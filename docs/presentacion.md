# Presentación — Hextech Archive (9 láminas)

Estética hextech: fondo azul abismo `#010A13`, dorado `#C8AA6E`, acento `#0AC8B9`; Cinzel para títulos. Exportar a `docs/presentacion.pdf` (**PENDIENTE**).

## 1. Proyecto e integrantes
- Hextech Archive: agente RAG sobre el lore de Runeterra
- Integrantes: **PENDIENTE:** nombres
- URLs públicas: **PENDIENTE**

*Notas:* presentar el nombre, el tema y quién hizo qué (Persona A: agente, ingesta, vectores; Persona B: frontend, auth, despliegue).

## 2. Problema
- El lore está disperso; los LLM generales alucinan datos
- Solución: responder solo con contexto recuperado, citar fuentes y rechazar si no hay información
- El usuario amplía la base subiendo documentos

*Notas:* mostrar el contraste: un chat genérico inventa; el nuestro dice "no sé" y explica por qué.

## 3. Arquitectura
- Diagrama: Vercel (React) → Supabase Auth → FastAPI en HF Space → LangGraph → Ollama + pgvector
- Todo el modelo corre local dentro del contenedor

*Notas:* recorrer el flujo de izquierda a derecha: login, JWT, API, agente, modelo, base vectorial.

## 4. Tecnologías
- React + Vite + Tailwind · FastAPI · LangChain + LangGraph
- Ollama `qwen2.5:3b` + `nomic-embed-text` · Supabase (Auth + pgvector, HNSW coseno)
- HF Spaces (Docker) + Vercel

*Notas:* justificar `qwen2.5:3b`: español decente y cabe en CPU. Mencionar la limitación de latencia.

## 5. Agente LangChain/LangGraph
- Nodos: validate_intent → retrieve → grade_context → generate / refuse → save_history
- Aristas condicionales tras validate_intent y grade_context
- 4 defensas anti-alucinación: umbral, grade_context, prompt restrictivo, rechazo + fuentes

*Notas:* mostrar el grafo (`docs/arquitectura.md`). Explicar que `grade_context` verifica de forma determinista (términos de la pregunta presentes en el contexto) y que `generate` rechaza con NO_INFO si aun así falta información. **PENDIENTE:** tasa de rechazo correcto de la evaluación.

## 6. Base vectorial y carga de documentos
- pgvector, `vector(768)`, índice HNSW, distancia coseno
- Carga en 6 pasos: recibir → extraer → fragmentar → embeddings → guardar → confirmar
- Formatos: PDF, TXT, MD, CSV, DOCX, JSON

*Notas:* explicar el solape entre fragmentos y el estado `processing/ready/error`.

## 7. Seguridad y usuarios
- Supabase Auth, validación del JWT (firma, expiración, audiencia)
- RLS y filtrado por `user_id`; corpus base solo lectura
- Límites de carga y CORS restringido

*Notas:* cada usuario solo ve sus documentos e historial.

## 8. Demostración
- Ver guion de demo abajo

*Notas:* calentar el Space antes con una pregunta; plan B: capturas o vídeo.

## 9. Conclusiones
- Un grafo explícito permite a un modelo 3B local responder con fiabilidad y rechazar sin contexto
- Retos: latencia en CPU, calibración del umbral. **PENDIENTE:** cifras reales
- Futuro: ingesta multimedia, administración, moderación

*Notas:* cerrar con las URLs y abrir preguntas.

---

# Guion de la demo (7-10 min)

Calentar el Space justo antes (hacer una pregunta) y tener plan B: capturas/vídeo si la latencia del 3B falla.

| # | Parte | Tiempo | Qué hacer |
|---|---|---|---|
| 1 | Tema y arquitectura | 1,5 min | Lámina 3; explicar el flujo y el modelo local |
| 2 | Login y UI | 0,5 min | Iniciar sesión, mostrar la estética |
| 3 | 2-3 preguntas respondidas con fuentes | 1,5 min | Ej.: "¿Quién es Jinx y de dónde viene?"; señalar las fuentes citadas |
| 4 | 2 preguntas rechazadas | 1 min | "¿Cuál es la mejor receta de sushi?" y "¿Quién es Briar?" |
| 5 | Subir `Briar.md` y repetir la pregunta | 1,5 min | Biblioteca de documentos → estado `ready` → "¿Quién es Briar?" responde con fuente `Briar.md` |
| 6 | Código | 1,5 min | `agents/graph.py`: nodos y aristas condicionales |
| 7 | URLs públicas del despliegue | 0,5 min | Mostrar frontend, backend `/health` y repositorio |

Total: 8 min (margen hasta 10).
