#!/usr/bin/env bash
# start.sh — one-command launcher for RAG Doc Reader
# Usage: ./start.sh [--model phi3] [--no-browser]
# ------------------------------------------------------------------------------------------------------------------─

set -euo pipefail

# --- Defaults ------------------------------------------------------------------------------------------------
MODEL="${MODEL:-llama3}"
OPEN_BROWSER=true
BACKEND_PORT=8000
FRONTEND_PORT=5173
BACKEND_PID=""
FRONTEND_PID=""
OLLAMA_STARTED=false

# --- Parse flags ---------------------------------------------------------------------------------------------
for arg in "$@"; do
  case $arg in
    --model=*) MODEL="${arg#*=}" ;;
    --no-browser) OPEN_BROWSER=false ;;
    --help|-h)
      echo "Usage: ./start.sh [--model=phi3] [--no-browser]"
      echo ""
      echo "  --model=NAME    Ollama model to use (default: llama3)"
      echo "                  Low RAM? Try: --model=phi3"
      echo "  --no-browser    Don't auto-open the browser"
      exit 0
      ;;
  esac
done

# --- Colors ---------------------------------------------------------------------------------------------------─
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${BLUE}[RAG]${RESET} $*"; }
ok()   { echo -e "${GREEN}[OK]${RESET}  $*"; }
warn() { echo -e "${YELLOW}[!!]${RESET}  $*"; }
err()  { echo -e "${RED}[ERR]${RESET} $*" >&2; }
hr()   { echo -e "${CYAN}---------------------------------------------------------------------${RESET}"; }

# --- Cleanup on exit ---------------------------------------------------------------------------------------
cleanup() {
  echo ""
  log "Shutting down..."
  [[ -n "$BACKEND_PID"  ]] && kill "$BACKEND_PID"  2>/dev/null && ok "Backend stopped"
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null && ok "Frontend stopped"
  if $OLLAMA_STARTED; then
    pkill -f "ollama serve" 2>/dev/null && ok "Ollama stopped"
  fi
  log "Done. Goodbye!"
}
trap cleanup EXIT INT TERM

# --- Banner ---------------------------------------------------------------------------------------------------─
hr
echo -e "${BOLD}  RAG Doc Reader${RESET}"
echo -e "  Model: ${CYAN}${MODEL}${RESET}"
hr
echo ""

# --- 1. Check prerequisites ------------------------------------------------------------------------------
log "Checking prerequisites..."

require() {
  if ! command -v "$1" &>/dev/null; then
    err "Missing: $1 — $2"
    exit 1
  fi
  ok "$1 found"
}

require python3    "Install from https://python.org"
require node       "Install from https://nodejs.org"
require npm        "Comes with Node.js"
require ollama     "Install from https://ollama.com"
echo ""

# --- 2. Ollama ------------------------------------------------------------------------------------------------─
log "Starting Ollama..."

if pgrep -f "ollama serve" > /dev/null 2>&1; then
  ok "Ollama already running"
else
  ollama serve > /tmp/ollama.log 2>&1 &
  OLLAMA_STARTED=true
  sleep 2
  ok "Ollama started (log: /tmp/ollama.log)"
fi

# Pull the model if it isn't cached
if ! ollama list | grep -qi "${MODEL}"; then
  warn "Model '${MODEL}' not found — pulling now (this may take a few minutes)..."
  ollama pull "${MODEL}"
  ok "Model '${MODEL}' ready"
else
  ok "Model '${MODEL}' already cached"
fi
echo ""

# --- 3. Python virtual environment ------------------------------------------------------------------─
log "Setting up Python environment..."

cd "$(dirname "$0")"   # ensure we're at the repo root

if [[ ! -d "backend/venv" ]]; then
  log "Creating venv..."
  python3 -m venv backend/venv
fi

# Activate
# shellcheck disable=SC1091
source backend/venv/bin/activate
ok "venv activated"

# Install/sync dependencies (idempotent)
pip install -q --upgrade pip
pip install -q -r backend/requirements.txt
ok "Backend dependencies ready"
echo ""

# --- 4. Backend .env ---------------------------------------------------------------------------------------─
if [[ ! -f "backend/.env" ]]; then
  warn ".env not found — creating from env.example.txt..."
  if [[ -f "backend/env.example.txt" ]]; then
    cp backend/env.example.txt backend/.env
    # Inject chosen model
    sed -i.bak "s/^LLM_MODEL=.*/LLM_MODEL=${MODEL}/" backend/.env
    rm -f backend/.env.bak
    ok ".env created with model=${MODEL}"
  else
    warn "No env.example.txt found — writing minimal .env"
    cat > backend/.env <<EOF
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=${MODEL}
EMBED_MODEL=nomic-embed-text
VECTOR_DB_PATH=./vector_store
EOF
    ok "Minimal .env written"
  fi
else
  ok ".env already exists"
fi
echo ""

# --- 5. Frontend dependencies ---------------------------------------------------------------------------
log "Checking frontend dependencies..."

if [[ ! -d "frontend/node_modules" ]]; then
  log "Running npm install..."
  (cd frontend && npm install --silent)
fi
ok "Frontend dependencies ready"
echo ""

# --- 6. Start backend ---------------------------------------------------------------------------------------
log "Starting FastAPI backend on :${BACKEND_PORT}..."

(cd backend && python main.py) > /tmp/rag-backend.log 2>&1 &
BACKEND_PID=$!

# Wait until the health endpoint responds (max 15s)
for i in $(seq 1 15); do
  if curl -sf "http://localhost:${BACKEND_PORT}/health" > /dev/null 2>&1; then
    ok "Backend healthy (pid ${BACKEND_PID})"
    break
  fi
  sleep 1
  if [[ $i -eq 15 ]]; then
    err "Backend failed to start. Check /tmp/rag-backend.log"
    cat /tmp/rag-backend.log
    exit 1
  fi
done
echo ""

# --- 7. Start frontend ------------------------------------------------------------------------------------─
log "Starting Vite dev server on :${FRONTEND_PORT}..."

(cd frontend && npm run dev -- --port "${FRONTEND_PORT}") > /tmp/rag-frontend.log 2>&1 &
FRONTEND_PID=$!

sleep 2
ok "Frontend started (pid ${FRONTEND_PID})"
echo ""

# --- 8. Open browser ---------------------------------------------------------------------------------------─
APP_URL="http://localhost:${FRONTEND_PORT}"

if $OPEN_BROWSER; then
  log "Opening ${APP_URL} ..."
  # Works on macOS, Linux (xdg-open), and WSL
  if command -v open &>/dev/null; then
    open "$APP_URL"
  elif command -v xdg-open &>/dev/null; then
    xdg-open "$APP_URL" &
  fi
fi

# --- 9. Summary ------------------------------------------------------------------------------------------------
hr
echo -e "${BOLD}  Everything is running!${RESET}"
echo ""
echo -e "  App:      ${CYAN}${APP_URL}${RESET}"
echo -e "  Backend:  ${CYAN}http://localhost:${BACKEND_PORT}/docs${RESET}"
echo -e "  Model:    ${CYAN}${MODEL}${RESET}"
echo ""
echo -e "  Logs:"
echo -e "    Backend:  ${YELLOW}tail -f /tmp/rag-backend.log${RESET}"
echo -e "    Frontend: ${YELLOW}tail -f /tmp/rag-frontend.log${RESET}"
echo -e "    Ollama:   ${YELLOW}tail -f /tmp/ollama.log${RESET}"
echo ""
echo -e "  Press ${BOLD}Ctrl+C${RESET} to stop all services."
hr

# Keep the script alive so trap fires on Ctrl+C
wait