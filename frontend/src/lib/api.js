import { supabase } from "./supabase";
import { parseSSE } from "./sse";

const BASE = import.meta.env.VITE_API_URL;

async function authHeaders() {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
  return { Authorization: `Bearer ${token}` };
}

async function readError(res) {
  try {
    const body = await res.json();
    return typeof body.detail === "string" ? body.detail : "La solicitud no es válida.";
  } catch {
    return `Error ${res.status}`;
  }
}

export async function api(path, options = {}) {
  const res = await fetch(BASE + path, {
    ...options,
    headers: { ...(options.headers || {}), ...(await authHeaders()) },
  });
  if (res.status === 401) {
    await supabase.auth.signOut();
    throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
  }
  if (!res.ok) throw new Error(await readError(res));
  return res.status === 204 ? null : res.json();
}

export async function streamChat(question, conversationId, onEvent, signal) {
  const res = await fetch(BASE + "/chat", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ question, conversation_id: conversationId || null }),
  });
  if (res.status === 401) {
    await supabase.auth.signOut();
    throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
  }
  if (!res.ok) throw new Error(await readError(res));
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const { events, rest } = parseSSE(buffer);
    buffer = rest;
    events.forEach(onEvent);
  }
}
