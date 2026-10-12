# Arquitectura

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

## Grafo del agente

```mermaid
flowchart TD
  S([inicio]) --> VI[validate_intent]
  VI -- válida --> R[retrieve]
  VI -- no válida --> RF[refuse]
  R --> GC[grade_context]
  GC -- contexto suficiente --> GE[generate]
  GC -- insuficiente --> RF
  GE --> SH[save_history]
  RF --> SH
  SH --> E([fin])
```

## Capas del backend

`controllers` (HTTP, validación de JWT) → `services` (ingesta, embeddings, agente) → `repositories` (pgvector, historial). Ollama corre dentro del mismo contenedor que FastAPI.

**PENDIENTE:** exportar el diagrama a `docs/arquitectura.png` (https://mermaid.live → Download PNG).
