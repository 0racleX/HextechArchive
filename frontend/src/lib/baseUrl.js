// Quita las barras finales de VITE_API_URL para que BASE + "/chat" nunca produzca "//chat".
export const normalizeBase = (url) => (url || "").replace(/\/+$/, "");
