# Stage 1: Download the embedding model at build time
FROM python:3.12-slim AS model-downloader
RUN pip install --no-cache-dir sentence-transformers==3.0.1
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Stage 2: Install all dependencies
FROM python:3.12-slim AS builder
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 3: lean runtime image
FROM python:3.12-slim
WORKDIR /app

# Copy installed packages — must match the python VERSION in this stage (3.12)
COPY --from=builder /usr/local/lib/python3.12/site-packages \
                    /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY --from=model-downloader /root/.cache /root/.cache

COPY backend/ .

RUN mkdir -p /app/vector_store

EXPOSE 8000
RUN useradd -m appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]