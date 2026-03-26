# Stage 1: Download the embedding model at build time
# meaning the model is baked into the image, so no 90 mb download at runtime

FROM python:3.12-slim AS model-downloader
RUN pip install --no-cache-dir senteence-transformers==3.0.1
RUN python -c "from sentence_transformers import SentenceTransformer;\
model = SentenceTransformer('all-MiniLM-L6-v2');\"

#Model is now cached in /root/.cache/huggingface/

# Stage 2: Install all dependencies
FROM python:3.12-slim AS builder
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


#stage 3: lean runtime image
FROM python:3.12-slim
WORKDIR /app

# Copy the installed dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages \
                    /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-downloaded model from model-downloader
COPY --from=model-downloader /root/.cache /root/.cache

# Copy application code
COPY backend/ .

# Create the vector store mount point
# (EFS will be mounted here by ECS — data persists across deployments)
RUN mkdir -p /app/vector_store

EXPOSE 8000
# Non-root user for security
RUN useradd -m appuser && chown -R appuser /app
USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]