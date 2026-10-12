import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import Frame from "../components/Frame";
import Message from "../components/Message";
import { api, streamChat } from "../lib/api";

const SUGGESTIONS = ["¿Quién es Jinx?", "¿Qué es Demacia?", "¿Qué hace la pasiva de Ahri?", "¿Qué son las Islas de la Sombra?"];

export default function Chat() {
  const [params, setParams] = useSearchParams();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const conversationId = params.get("c");
  const bottom = useRef(null);

  useEffect(() => {
    setError("");
    if (!conversationId) return setMessages([]);
    api(`/conversations/${conversationId}`)
      .then((c) => setMessages(c.messages.map((m) => ({ ...m, sources: m.sources || [] }))))
      .catch((e) => setError(e.message));
  }, [conversationId]);

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  async function send(text) {
    const question = text.trim();
    if (!question || busy) return;
    if (question.length > 1000) return setError("La pregunta no puede superar 1000 caracteres.");
    setError(""); setInput(""); setBusy(true);
    setMessages((m) => [...m, { role: "user", content: question }, { role: "assistant", content: "", pending: true }]);
    const patchLast = (patch) => setMessages((m) => m.map((x, i) => (i === m.length - 1 ? { ...x, ...patch } : x)));
    let streamed = "";
    try {
      await streamChat(question, conversationId, (ev) => {
        if (ev.type === "token") { streamed += ev.text; patchLast({ content: streamed }); }
        if (ev.type === "final") {
          patchLast({ content: ev.answer, sources: ev.sources, refused: ev.refused, pending: false });
          if (!conversationId) setParams({ c: ev.conversation_id }, { replace: true });
        }
        if (ev.type === "error") { setError(ev.message); setMessages((m) => m.filter((x) => !x.pending)); }
      });
    } catch (e) {
      setError(e.message);
      setMessages((m) => m.filter((x) => !x.pending));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Frame className="flex h-[calc(100vh-150px)] min-h-[420px] flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto p-5" aria-live="polite">
        {messages.length === 0 && (
          <div className="grid h-full place-items-center text-center">
            <div>
              <h2 className="mb-2 text-2xl">Pregunta a los archivos de Runeterra</h2>
              <p className="mb-5 italic text-ink">Solo respondo con lo que consta en mi base de conocimiento.</p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="btn-ghost" onClick={() => send(s)}>{s}</button>
                ))}
              </div>
            </div>
          </div>
        )}
        {messages.map((m, i) => <Message key={i} {...m} />)}
        <div ref={bottom} />
      </div>
      {error && <p role="alert" className="border-t border-ember/40 bg-ember/10 px-5 py-2 text-ember">{error}</p>}
      <form className="flex gap-3 border-t border-gold/30 p-4" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <input className="field" placeholder="¿Qué deseas saber, invocador?" value={input} maxLength={1000}
               onChange={(e) => setInput(e.target.value)} disabled={busy} aria-label="Pregunta" />
        <button className="btn-gold" disabled={busy || !input.trim()}>{busy ? "…" : "Preguntar"}</button>
      </form>
    </Frame>
  );
}
