#!/bin/bash
set -e
ollama serve &
ready=0
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then ready=1; break; fi
  sleep 1
done
if [ "$ready" != "1" ]; then
  echo "ADVERTENCIA: Ollama no respondio tras 30 s; se inicia uvicorn de todos modos." >&2
fi
# Calentar el modelo en segundo plano para no retrasar la apertura del puerto
(
  curl -s http://127.0.0.1:11434/api/generate -d "{\"model\":\"${CHAT_MODEL:-qwen2.5:3b}\",\"prompt\":\"hola\",\"stream\":false,\"options\":{\"num_predict\":1}}" >/dev/null || true
) &
exec uvicorn app.main:app --host 0.0.0.0 --port 7860
