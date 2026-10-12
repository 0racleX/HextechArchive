# Hextech Archive

Aplicación web en la que un usuario autenticado conversa con un agente sobre el **lore de Runeterra y los campeones de League of Legends**. El agente (LangChain + LangGraph, modelo local con Ollama) responde **solo** con información recuperada de una base vectorial (pgvector) y cita sus fuentes; si no hay contexto suficiente, rechaza explícitamente. El usuario puede subir documentos (PDF, TXT, MD, CSV, DOCX, JSON) para ampliar la base de conocimiento.

- Frontend: **PENDIENTE: URL de Vercel** `https://<tu-app>.vercel.app`
- Backend: **PENDIENTE: URL del Space** `https://<usuario>-hextech-archive.hf.space`

## Arquitectura

```mermaid
flowchart LR
  U[Usuario] --> F[Frontend React · Vercel]
  F -- login --> A[Supabase Auth]
  F -- JWT --> B[FastAPI · HF Space]
  B --> G[Agente LangGraph]
  G --> O[Ollama qwen2.5:3b + nomic-embed-text]
  G --> V[(Supabase pgvector)]
  B --> V
```

Más detalle (grafo del agente) en [docs/arquitectura.md](docs/arquitectura.md).

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | React + Vite + Tailwind (Vercel) |
| Backend | FastAPI (Python 3.11) |
| Agente | LangChain + LangGraph |
| LLM local | Ollama `qwen2.5:3b` (alternativa: `llama3.2:3b`) |
| Embeddings | Ollama `nomic-embed-text` (768 dim) |
| Auth | Supabase Auth (JWT) |
| Base vectorial | PostgreSQL + pgvector (Supabase), índice HNSW coseno |
| Despliegue | Hugging Face Spaces (Docker, CPU) + Vercel |

## Requisitos

- Python 3.11
- Node 20
- [Ollama](https://ollama.com)
- Un proyecto de Supabase (gratuito)

## Ejecución local

1. **Supabase:** crear un proyecto y ejecutar `backend/supabase/migrations/001_init.sql` en el SQL Editor. Crear un usuario en *Authentication → Users*.
2. **Variables:** copiar `.env.example` a `backend/.env` (variables de backend) y a `frontend/.env` (las `VITE_*`), y rellenarlas.
3. **Modelos:**
   ```bash
   ollama pull qwen2.5:3b
   ollama pull nomic-embed-text
   ```
4. **Backend:**
   ```bash
   cd backend
   python -m venv .venv && .venv\Scripts\activate   # Linux/macOS: source .venv/bin/activate
   pip install -r requirements.txt
   python -m uvicorn app.main:app --reload --port 8000
   ```
5. **Corpus base:** `python -m scripts.seed_corpus` (desde `backend/`, con el venv activo).
6. **Frontend:**
   ```bash
   cd frontend
   npm install
   npm run dev      # http://localhost:5173
   ```
7. **Tests del backend:** `cd backend && pip install -r requirements-dev.txt && python -m pytest`.

## Despliegue

### Backend en Hugging Face Spaces

1. Crear un Space en https://huggingface.co/new-space: nombre `hextech-archive`, SDK **Docker**, hardware **CPU basic (free)**.
2. En *Settings → Variables and secrets* añadir como *Secrets*: `DATABASE_URL` y `SUPABASE_JWT_SECRET` (o `SUPABASE_JWKS_URL`); como *Variables*: `CHAT_MODEL=qwen2.5:3b`, `EMBED_MODEL=nomic-embed-text`, `SIMILARITY_THRESHOLD=<valor calibrado>`, `TOP_K=5`, `MAX_UPLOAD_MB=10`, `CORS_ORIGINS=https://<tu-app>.vercel.app,http://localhost:5173`.
3. Subir solo `backend/` como raíz del Space (la cabecera YAML está en `backend/README.md`):
   ```bash
   git remote add space https://huggingface.co/spaces/<usuario>/hextech-archive
   git subtree push --prefix backend space main
   ```
   Si rechaza por historial divergente: ``git push space `git subtree split --prefix backend main`:main --force``.
   Nota: los modelos se descargan al construir la imagen; cambiar `CHAT_MODEL` o `EMBED_MODEL` exige reconstruir la imagen.
4. Esperar el build (10-20 min la primera vez; descarga los modelos). Comprobar `curl https://<usuario>-hextech-archive.hf.space/health` → `{"status":"ok"}`.

### Frontend en Vercel

1. Subir el repo a GitHub e importarlo en https://vercel.com/new con **Root Directory = `frontend`** (framework Vite).
2. Variables de entorno: `VITE_API_URL=https://<usuario>-hextech-archive.hf.space`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
3. En Supabase → *Authentication → URL Configuration* añadir la URL de Vercel como *Site URL*, y confirmar que `CORS_ORIGINS` del Space la incluye exactamente.

## Variables de entorno

Copiadas de `.env.example`.

| Variable | Dónde | Descripción | Ejemplo / defecto |
|---|---|---|---|
| `DATABASE_URL` | Backend | Conexión Postgres de Supabase (pooler) | `postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres` |
| `SUPABASE_JWT_SECRET` | Backend | Secreto para validar JWT (o usar JWKS) | vacío |
| `SUPABASE_JWKS_URL` | Backend | URL JWKS (alternativa al secreto) | vacío |
| `OLLAMA_BASE_URL` | Backend | Servidor Ollama | `http://localhost:11434` |
| `CHAT_MODEL` | Backend | Modelo de chat | `qwen2.5:3b` |
| `EMBED_MODEL` | Backend | Modelo de embeddings | `nomic-embed-text` |
| `SIMILARITY_THRESHOLD` | Backend | Umbral mínimo de similitud | `0.55` |
| `TOP_K` | Backend | Fragmentos recuperados | `5` |
| `MAX_UPLOAD_MB` | Backend | Tamaño máximo de subida | `10` |
| `CORS_ORIGINS` | Backend | Orígenes permitidos (coma) | `http://localhost:5173` |
| `VITE_API_URL` | Frontend | URL del backend | `http://localhost:8000` |
| `VITE_SUPABASE_URL` | Frontend | URL del proyecto Supabase | vacío |
| `VITE_SUPABASE_ANON_KEY` | Frontend | Clave anónima de Supabase | vacío |

## Capturas

**PENDIENTE:** añadir capturas en `docs/capturas/` (login, chat con fuentes, rechazo, documentos, historial) y enlazarlas aquí.

## Estructura del repositorio

```
hextech-archive/
├── backend/    FastAPI: app/ (controllers, services, repositories, security, loaders, agents),
│               scripts/, tests/, supabase/migrations/, Dockerfile, start.sh, README.md
├── frontend/   React + Vite + Tailwind
├── docs/       arquitectura.md, documento-tecnico.md, presentacion.md, capturas/
├── .env.example
└── README.md
```

## Documentación

- [Arquitectura](docs/arquitectura.md)
- [Documento técnico](docs/documento-tecnico.md)
- [Presentación y guion de demo](docs/presentacion.md)

## Atribución

Datos de campeones de Data Dragon (Riot Games); textos de la wiki de League of Legends en Fandom (CC BY-SA). Proyecto educativo sin fines comerciales; no está respaldado por Riot Games. League of Legends y Runeterra son marcas de Riot Games, Inc.
