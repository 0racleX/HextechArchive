FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl zstd ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://ollama.com/install.sh | sh

ENV OLLAMA_MODELS=/opt/ollama-models \
    OLLAMA_KEEP_ALIVE=24h \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_BASE_URL=http://127.0.0.1:11434

# Descargar los modelos durante el build para que el arranque sea rápido
RUN mkdir -p $OLLAMA_MODELS \
    && (ollama serve & \
        ready=0; \
        for i in $(seq 1 60); do \
          if curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then ready=1; break; fi; \
          sleep 1; \
        done; \
        [ "$ready" = "1" ] || { echo "Ollama no arranco durante el build" >&2; exit 1; }; \
        ollama pull qwen2.5:3b && ollama pull nomic-embed-text && sleep 2) \
    && chmod -R a+rwX $OLLAMA_MODELS

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY start.sh .
RUN chmod +x start.sh

# Hugging Face Spaces ejecuta como usuario 1000
RUN useradd -m -u 1000 user && chown -R user /app
USER user
EXPOSE 7860
CMD ["./start.sh"]
