#!/bin/bash
set -e
ollama serve &
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:11434/api/tags >/dev/null && break
  sleep 1
done
# Calentar el modelo para que la primera pregunta no pague la carga
curl -s http://127.0.0.1:11434/api/generate -d '{"model":"qwen2.5:3b","prompt":"hola","stream":false,"options":{"num_predict":1}}' >/dev/null || true
exec uvicorn app.main:app --host 0.0.0.0 --port 7860
