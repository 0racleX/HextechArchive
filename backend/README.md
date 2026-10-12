---
title: Hextech Archive API
emoji: 🔮
colorFrom: yellow
colorTo: blue
sdk: docker
app_port: 7860
---

# Hextech Archive — Backend

API FastAPI del agente RAG sobre el lore de Runeterra. Capas: `controllers` (HTTP) → `services` → `repositories` (Postgres/pgvector). El agente LangGraph usa Ollama (`qwen2.5:3b` + `nomic-embed-text`) y Supabase (Auth + pgvector).

Endpoints (todos exigen `Authorization: Bearer <JWT de Supabase>` salvo `/health`): `GET /health`, `GET /me`, `POST /documents` (multipart), `GET /documents`, `DELETE /documents/{id}`, `POST /chat` (streaming SSE: eventos `step`, `token`, `final`, `error`), `GET /conversations` y `GET /conversations/{id}`.

## Requisitos

- Python 3.11
- Un proyecto Supabase con la migración `supabase/migrations/001_init.sql` aplicada (extensión `vector`, tablas, índice HNSW y RLS).
- [Ollama](https://ollama.com) en ejecución con los modelos descargados:
  ```bash
  ollama pull qwen2.5:3b
  ollama pull nomic-embed-text
  ```

## Instalación

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
pip install -r requirements-dev.txt   # solo para ejecutar los tests
cp ../.env.example .env         # y rellenar los valores
```

## Variables de entorno (`backend/.env`)

| Variable | Descripción | Valor por defecto / ejemplo |
|---|---|---|
| `DATABASE_URL` | Cadena de conexión Postgres de Supabase (pooler) | `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres` |
| `SUPABASE_JWT_SECRET` | Secreto HS256 del proyecto (solo claves heredadas HS256) | vacío |
| `SUPABASE_JWKS_URL` | URL JWKS para tokens asimétricos ES256/RS256 (`https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json`) | vacío |
| `OLLAMA_BASE_URL` | URL del servidor Ollama | `http://localhost:11434` |
| `CHAT_MODEL` | Modelo de chat | `qwen2.5:3b` |
| `EMBED_MODEL` | Modelo de embeddings (768 dim) | `nomic-embed-text` |
| `SIMILARITY_THRESHOLD` | Umbral mínimo de similitud coseno | `0.55` (a calibrar) |
| `TOP_K` | Fragmentos recuperados | `5` |
| `MAX_UPLOAD_MB` | Tamaño máximo de archivo subido | `10` |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma | `http://localhost:5173` |

Se necesita al menos uno de `SUPABASE_JWT_SECRET` o `SUPABASE_JWKS_URL`; sin ninguno la autenticación falla cerrada (rechaza todo).

**Qué variable usar:** abre *Project Settings → JWT Keys* (JWT Signing Keys) en Supabase. Si el proyecto usa claves asimétricas (**ES256/RS256**, lo normal en proyectos nuevos) define `SUPABASE_JWKS_URL` y deja `SUPABASE_JWT_SECRET` vacío; si usa el secreto heredado (**HS256**) define `SUPABASE_JWT_SECRET`. Si solo pones el secreto en un proyecto ES256, **todas** las peticiones devuelven 401. Diagnóstico: mira el `alg` de la cabecera del token (jwt.io) y el log del backend (`Auth misconfigured…` si falta la clave).

## Ejecutar

```bash
python -m uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/health        # {"status":"ok"}
```

## Tests

```bash
python -m pytest
```

Los tests usan dobles de prueba (LLM/embeddings falsos); `test_repositories_integration.py` requiere una base Postgres real con pgvector y se omite si no se define `TEST_DATABASE_URL`.

## Cargar el corpus base

Con Ollama y la base de datos disponibles:

```bash
python -m scripts.seed_corpus
```

(Descarga los campeones de Data Dragon (`es_MX`) y las regiones de la wiki de LoL en español en Fandom (`action=parse`), genera embeddings y los guarda como corpus compartido con `user_id` nulo. Termina con código distinto de 0 si algún documento falla; al repetirlo, borra y reintenta los que quedaron en error.)

## Docker / Hugging Face Space

El `Dockerfile` instala Ollama, descarga `qwen2.5:3b` y `nomic-embed-text` durante el build, se ejecuta como usuario 1000 y `start.sh` arranca Ollama y luego `uvicorn` en el puerto 7860.

```bash
docker build -t hextech-backend .
docker run --rm -p 7860:7860 --env-file .env hextech-backend
```

Nota: los modelos se descargan al construir la imagen; cambiar `CHAT_MODEL` o `EMBED_MODEL` exige reconstruir la imagen.

Alternativa local: desde la raíz del repo, `docker compose up --build` construye esta imagen (con su propio Ollama y modelos) y la expone en `http://localhost:8000`, usando `backend/.env`.

Los pasos de despliegue del Space están en el [README raíz](../README.md#despliegue).
