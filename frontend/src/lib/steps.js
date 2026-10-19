// Etiquetas legibles (es) para los nodos del grafo del agente (eventos SSE `step`).
export const STEP_LABELS = {
  validate_intent: "Entendiendo la pregunta",
  pick_topic: "Eligiendo el tema",
  catalog_answer: "Consultando el catálogo",
  retrieve: "Buscando en el archivo",
  grade_context: "Verificando el contexto",
  generate: "Redactando respuesta",
  social: "Preparando respuesta",
  refuse: "Preparando respuesta",
  save_history: "Guardando la conversación",
};

export const DEFAULT_STEP_LABEL = "Consultando los archivos";

export function stepLabel(node) {
  return STEP_LABELS[node] ?? DEFAULT_STEP_LABEL;
}
