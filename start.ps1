# start.ps1 -- one-command launcher for RAG Doc Reader (Windows)
# Usage:  .\start.ps1
#         .\start.ps1 -Model phi3
#         .\start.ps1 -NoBrowser
#
# If you hit an execution-policy error, run once in an admin shell:
#   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
# =============================================================================

param(
    [string] $Model      = "llama3",
    [switch] $NoBrowser,
    [switch] $Help
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

# == Ports =====================================================================
$BACKEND_PORT  = 8000
$FRONTEND_PORT = 5173

# == Job tracking (so we can kill them on exit) ================================
$BackendJob   = $null
$FrontendJob  = $null
$OllamaJob    = $null
$OllamaStarted = $false

# == Colors via Write-Host =====================================================
function Log  ($msg) { Write-Host "[RAG] " -ForegroundColor Cyan    -NoNewline; Write-Host $msg }
function Ok   ($msg) { Write-Host "[OK]  " -ForegroundColor Green   -NoNewline; Write-Host $msg }
function Warn ($msg) { Write-Host "[!!]  " -ForegroundColor Yellow  -NoNewline; Write-Host $msg }
function Err  ($msg) { Write-Host "[ERR] " -ForegroundColor Red     -NoNewline; Write-Host $msg }
function Hr   ()     { Write-Host ("=" * 50) -ForegroundColor DarkCyan }

# == Cleanup -- runs on Ctrl+C or script exit ===================================
function Cleanup {
    Write-Host ""
    Log "Shutting down..."

    if ($null -ne $BackendJob) {
        Stop-Job  $BackendJob  -ErrorAction SilentlyContinue
        Remove-Job $BackendJob -ErrorAction SilentlyContinue
        Ok "Backend stopped"
    }
    if ($null -ne $FrontendJob) {
        Stop-Job  $FrontendJob  -ErrorAction SilentlyContinue
        Remove-Job $FrontendJob -ErrorAction SilentlyContinue
        Ok "Frontend stopped"
    }
    if ($OllamaStarted) {
        Get-Process -Name "ollama" -ErrorAction SilentlyContinue | Stop-Process -Force
        Ok "Ollama stopped"
    }
    Log "Done. Goodbye!"
}

# Register cleanup for Ctrl+C
[Console]::TreatControlCAsInput = $false
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup }

# == Help ======================================================================
if ($Help) {
    Write-Host ""
    Write-Host "Usage: .\start.ps1 [-Model NAME] [-NoBrowser]"
    Write-Host ""
    Write-Host "  -Model NAME   Ollama model to use (default: llama3)"
    Write-Host "                  Low RAM (< 8 GB)? Try: -Model phi3"
    Write-Host "  -NoBrowser      Don't auto-open the browser"
    Write-Host ""
    exit 0
}

# == Banner ====================================================================
Hr
Write-Host "  RAG Doc Reader" -ForegroundColor White
Write-Host "  Model: " -NoNewline; Write-Host $Model -ForegroundColor Cyan
Hr
Write-Host ""

# == 1. Check prerequisites ====================================================
Log "Checking prerequisites..."

function Require ($cmd, $hint) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Err "Missing: $cmd -- $hint"
        exit 1
    }
    Ok "$cmd found"
}

Require "python"  "Install from https://python.org  (add to PATH)"
Require "node"    "Install from https://nodejs.org"
Require "npm"     "Comes with Node.js"
Require "ollama"  "Install from https://ollama.com"
Write-Host ""

# == 2. Ollama =================================================================
Log "Starting Ollama..."

$ollamaRunning = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if ($ollamaRunning) {
    Ok "Ollama already running"
} else {
    $OllamaJob    = Start-Job -ScriptBlock { ollama serve 2>&1 | Out-File "$env:TEMP\ollama.log" -Encoding utf8 }
    $OllamaStarted = $true
    Start-Sleep -Seconds 2
    Ok "Ollama started  (log: $env:TEMP\ollama.log)"
}

# Pull model if not cached
$modelList = & ollama list 2>&1
if ($modelList -notmatch [regex]::Escape($Model)) {
    Warn "Model '$Model' not found -- pulling now (may take a few minutes)..."
    & ollama pull $Model
    if ($LASTEXITCODE -ne 0) { Err "Failed to pull model '$Model'"; exit 1 }
    Ok "Model '$Model' ready"
} else {
    Ok "Model '$Model' already cached"
}
Write-Host ""

# == 3. Python virtual environment =============================================
Log "Setting up Python environment..."

# Move to the repo root (same directory as this script)
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoRoot

$VenvDir    = Join-Path $RepoRoot "backend\venv"
$VenvPython = Join-Path $VenvDir  "Scripts\python.exe"
$VenvPip    = Join-Path $VenvDir  "Scripts\pip.exe"

if (-not (Test-Path $VenvDir)) {
    Log "Creating venv..."
    $Py313 = "C:\Users\bhagy\AppData\Local\Programs\Python\Python313\python.exe"
    if (-not (Test-Path $Py313)) { $Py313 = "python" }
    & $Py313 -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Err "python -m venv failed"; exit 1 }
}
Ok "venv ready"

# Upgrade pip silently then install requirements
& $VenvPip install -q --upgrade pip
& $VenvPip install -q -r (Join-Path $RepoRoot "backend\requirements.txt")
if ($LASTEXITCODE -ne 0) { Err "pip install failed -- check backend\requirements.txt"; exit 1 }
Ok "Backend dependencies ready"
Write-Host ""

# == 4. Backend .env ===========================================================
$EnvFile     = Join-Path $RepoRoot "backend\.env"
$EnvExample  = Join-Path $RepoRoot "backend\env.example.txt"

if (-not (Test-Path $EnvFile)) {
    Warn ".env not found -- creating..."
    if (Test-Path $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        # Patch the model line
        (Get-Content $EnvFile) -replace '^LLM_MODEL=.*', "LLM_MODEL=$Model" |
            Set-Content $EnvFile -Encoding UTF8
        Ok ".env created with model=$Model"
    } else {
        Warn "No env.example.txt -- writing minimal .env"
        @"
LLM_PROVIDER=ollama
OLLAMA_HOST=http://localhost:11434
LLM_MODEL=$Model
EMBED_MODEL=nomic-embed-text
VECTOR_DB_PATH=./vector_store
"@ | Set-Content $EnvFile -Encoding UTF8
        Ok "Minimal .env written"
    }
} else {
    Ok ".env already exists"
}
Write-Host ""

# == 5. Frontend dependencies ==================================================
Log "Checking frontend dependencies..."

$FrontendDir = Join-Path $RepoRoot "frontend"
$NodeModules = Join-Path $FrontendDir "node_modules"

if (-not (Test-Path $NodeModules)) {
    Log "Running npm install..."
    Push-Location $FrontendDir
    & npm install --silent
    if ($LASTEXITCODE -ne 0) { Err "npm install failed"; Pop-Location; exit 1 }
    Pop-Location
}
Ok "Frontend dependencies ready"
Write-Host ""

# == 6. Start backend ==========================================================
Log "Starting FastAPI backend on :$BACKEND_PORT..."

$BackendLog = "$env:TEMP\rag-backend.log"
$BackendDir = Join-Path $RepoRoot "backend"

$BackendJob = Start-Job -ScriptBlock {
    param($python, $dir, $log)
    Set-Location $dir
    # Isolate streams from PowerShell using cmd /c
    cmd /c "`"$python`" main.py > `"$log`" 2>&1"
} -ArgumentList $VenvPython, $BackendDir, $BackendLog

Start-Sleep -Seconds 3

# Wait up to 15 s for the health endpoint
$healthy = $false
for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        # Using 127.0.0.1 forces Windows to use the IPv4 loopback directly
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:${BACKEND_PORT}/health" `
                                  -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($resp.StatusCode -eq 200) { $healthy = $true; break }
    } catch { <# not up yet #> }
}

if (-not $healthy) {
    Err "Backend failed to start after 15 s. Check: $BackendLog"
    Get-Content $BackendLog -ErrorAction SilentlyContinue | Select-Object -Last 20
    Cleanup; exit 1
}
Ok "Backend healthy"
Write-Host ""
# == 7. Start frontend =========================================================
Log "Starting Vite dev server on :$FRONTEND_PORT..."

$FrontendLog = "$env:TEMP\rag-frontend.log"

$FrontendJob = Start-Job -ScriptBlock {
    param($dir, $port, $log)
    Set-Location $dir
    & npm run dev -- --port $port 2>&1 | Out-File $log -Encoding utf8
} -ArgumentList $FrontendDir, $FRONTEND_PORT, $FrontendLog

Start-Sleep -Seconds 3
Ok "Frontend started"
Write-Host ""

# == 8. Open browser ===========================================================
$AppUrl = "http://localhost:$FRONTEND_PORT"

if (-not $NoBrowser) {
    Log "Opening $AppUrl ..."
    Start-Process $AppUrl
}

# == 9. Summary ================================================================
Hr
Write-Host "  Everything is running!" -ForegroundColor White
Write-Host ""
Write-Host "  App:     " -NoNewline; Write-Host $AppUrl                                   -ForegroundColor Cyan
Write-Host "  Backend: " -NoNewline; Write-Host "http://localhost:$BACKEND_PORT/docs"      -ForegroundColor Cyan
Write-Host "  Model:   " -NoNewline; Write-Host $Model                                    -ForegroundColor Cyan
Write-Host ""
Write-Host "  Logs:"
Write-Host "    Backend:  " -NoNewline; Write-Host $BackendLog  -ForegroundColor Yellow
Write-Host "    Frontend: " -NoNewline; Write-Host $FrontendLog -ForegroundColor Yellow
Write-Host "    Ollama:   " -NoNewline; Write-Host "$env:TEMP\ollama.log" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Press " -NoNewline
Write-Host "Ctrl+C" -ForegroundColor Red -NoNewline
Write-Host " to stop all services."
Hr

# == 10. Keep alive -- stream job output so logs appear in the terminal =========
try {
    $LastBackendLine  = 0
    $LastFrontendLine = 0

    while ($true) {
        if (Test-Path $BackendLog) {
            $bLines = Get-Content $BackendLog -ErrorAction SilentlyContinue
            if ($bLines.Count -gt $LastBackendLine) {
                $bLines[$LastBackendLine..($bLines.Count-1)] | ForEach-Object { Write-Host "[backend]  $_" -ForegroundColor DarkGray }
                $LastBackendLine = $bLines.Count
            }
        }

        if (Test-Path $FrontendLog) {
            $fLines = Get-Content $FrontendLog -ErrorAction SilentlyContinue
            if ($fLines.Count -gt $LastFrontendLine) {
                $fLines[$LastFrontendLine..($fLines.Count-1)] | ForEach-Object { Write-Host "[frontend] $_" -ForegroundColor DarkGray }
                $LastFrontendLine = $fLines.Count
            }
        }

        Start-Sleep -Seconds 1
    }
} finally {
    Cleanup
}