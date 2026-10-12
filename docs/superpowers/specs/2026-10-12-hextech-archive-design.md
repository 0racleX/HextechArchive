# Hextech Archive — Especificación de diseño

Fecha: 2026-10-12
Origen: `trabajo agente.pdf` (Agente inteligente con LangChain, LangGraph y RAG)

## 1. Objetivo

Aplicación web en la que un usuario autenticado conversa con un agente que responde preguntas sobre el **lore de Runeterra y los campeones de League of Legends**, solo con información recuperada de una base vectorial. Si no hay contexto suficiente, rechaza explícitamente. El usuario puede subir documentos para ampliar la base de conocimiento.

Criterios de éxito (mínimos del PDF, sección 6.1):
- Backend y frontend funcionales, con autenticación.
- Agente construido en código con LangChain y LangGraph.
- Modelo local en funcionamiento (Ollama).
- Base vectorial integrada y carga de documentos operativa.
- Respuestas fundamentadas en el contexto recuperado y rechazo explícito sin información.
- Despliegue en la nube con URLs públicas y repositorio documentado.

## 2. Restricciones y decisiones

| Tema | Decisión |
|---|---|
| Equipo | Pareja |
| Hardware de desarrollo | 32 GB RAM, Intel Iris Xe (sin GPU dedicada): inferencia en CPU |
| Backend | FastAPI (Python) |
| Frontend | React + Vite + Tailwind |
| Auth | Supabase Auth (JWT) |
| Vector DB | PostgreSQL + pgvector en Supabase |
| LLM local | Ollama, `qwen2.5:3b` (alternativa documentada: `llama3.2:3b`) |
| Embeddings | Ollama `nomic-embed-text` (768 dim) |
| Orquestación | LangChain + LangGraph, escritos en código (sin herramientas visuales) |
| Despliegue backend | Hugging Face Spaces (Docker, CPU, 16 GB RAM) con Ollama dentro del contenedor |
| Despliegue frontend | Vercel |

Riesgo: el 3B en CPU compartida puede tardar 20-40 s por respuesta. Mitigación: streaming SSE, `num_ctx` reducido, `top_k` pequeño, y prueba de modelo alterno si la latencia es inaceptable.

## 3. Arquitectura

```
Vercel (React + Vite)  --JWT-->  Hugging Face Space (Docker)
   login con Supabase            ├─ FastAPI (controllers → services → repos)
                                 ├─ Agente LangGraph
                                 └─ Ollama: qwen2.5:3b + nomic-embed-text
                                          |
                             Supabase: Auth + Postgres/pgvector
                             (documents, chunks, conversations, messages)
```

## 4. Agente LangGraph

Estado: `question`, `intent_ok`, `chunks[]` (contenido, score, fuente), `context_ok`, `answer`, `sources[]`, `refused`.

Nodos:
1. `validate_intent`: descarta mensajes vacíos, saludos y preguntas claramente ajenas a LoL/Runeterra. Si no es válido → `refuse` (o respuesta de aclaración).
2. `retrieve`: búsqueda por similitud en pgvector (top-k, filtrada por corpus compartido + documentos del usuario).
3. `grade_context`: (a) umbral mínimo de similitud sobre los chunks; (b) verificación del modelo "¿este contexto permite responder la pregunta? sí/no". Si falla → `refuse`.
4. `generate`: responde solo con el contexto, en español, citando las fuentes. El prompt prohíbe usar conocimiento externo.
5. `refuse`: devuelve el mensaje fijo "No tengo suficiente información en mi base de conocimiento para responder esa pregunta." y sugiere subir documentos relacionados.
6. `save_history`: persiste la interacción (pregunta, respuesta, fuentes, bandera `refused`).

Aristas condicionales: tras `validate_intent` y tras `grade_context`. Todas las rutas terminan en `save_history`.

### Control de alucinaciones (el PDF pide ≥2; se implementan 4)
- Umbral mínimo de similitud.
- Nodo dedicado de validación del contexto.
- Prompt restrictivo (solo contexto recuperado).
- Fuentes/fragmentos visibles en la respuesta, y rechazo explícito.

## 5. Ingesta de documentos

Flujo: recibir archivo → extraer texto → dividir en fragmentos (con solape) → generar embeddings → guardar en pgvector con `document_id` → confirmar al usuario.

Formatos: PDF, TXT, MD, CSV, DOCX, JSON. Multimedia (JPG/MP4/MP3) queda fuera de alcance (el PDF solo lo sugiere); se documenta como trabajo futuro. Se valida tipo y tamaño máximo.

Corpus base (script `seed_corpus.py`): Data Dragon en español (campeones: lore, habilidades, roles), Universe de Riot y wikis (CC BY-SA, con atribución en el documento técnico). Se reservan 1-2 campeones o regiones fuera del corpus para la demo de carga en vivo.

## 6. Datos (Postgres/Supabase)

- `documents(id, user_id, name, type, status, created_at)`
- `chunks(id, document_id, content, metadata jsonb, embedding vector(768))`, índice HNSW
- `conversations(id, user_id, title, created_at)`
- `messages(id, conversation_id, role, content, sources jsonb, refused bool, created_at)`

RLS por `user_id` en todas las tablas. El corpus base tiene `user_id` nulo y es de solo lectura para todos.

## 7. API REST

Todos los endpoints exigen `Authorization: Bearer <JWT>` (validación de firma, expiración y audiencia), excepto `GET /health`.

- `POST /chat` (streaming SSE; `conversation_id` opcional)
- `GET /conversations`, `GET /conversations/{id}`
- `POST /documents` (multipart), `GET /documents`, `DELETE /documents/{id}`
- `GET /me`

Registro, login y cierre de sesión los hace el frontend con Supabase Auth.

## 8. Frontend

Pantallas: Login/Registro, Chat (fuentes citadas), Biblioteca de documentos (estados procesando/listo/error), Historial. Rutas protegidas, validación de formularios y mensajes de error cuando el agente no puede responder.

Estética "Runeterra / hextech":
- Paleta: azul abismo `#010A13`, dorado `#C8AA6E`, azul hextech `#0AC8B9`.
- Tipografías: Cinzel (títulos), Cormorant Garamond (texto narrativo), JetBrains Mono (fuentes y scores).
- Marcos dorados ornamentales, brillos hextech al enviar, chat tipo grimorio con fuentes como runas, login con partículas.
- Responsive y accesible (contraste, foco visible, `prefers-reduced-motion`).

## 9. Estructura del repositorio

```
hextech-archive/
├── backend/ (app/{main,config}.py, controllers/, services/, agents/, vectorstore/,
│             security/, loaders/, scripts/seed_corpus.py, tests/, Dockerfile,
│             start.sh, requirements.txt)
├── frontend/ (src/, public/, package.json)
├── docs/ (arquitectura.png, documento-tecnico.pdf, presentacion.pdf)
├── docker-compose.yml, .env.example, README.md
```

## 10. Pruebas

- Tests del grafo con LLM falso: ruta de respuesta y ruta de rechazo.
- Tests de validación del JWT (válido, expirado, ausente).
- Set de ~20 preguntas de evaluación (válidas y fuera de tema) para medir tasa de rechazo correcto.

## 11. Entregables y reparto

Entregables: repositorio GitHub, documento técnico (14 apartados, PDF), sustentación de 7-10 min con demo, 8-12 diapositivas (PDF).

- Persona A: agente LangGraph, ingesta, pgvector, modelo local.
- Persona B: frontend, auth, API de historial y documentos, despliegue en Vercel.
- Juntos: corpus, documento técnico, diapositivas, sustentación.

## 12. Fuera de alcance

Ingesta multimedia (JPG/MP4/MP3), roles de administrador, y moderación avanzada de contenido subido.
