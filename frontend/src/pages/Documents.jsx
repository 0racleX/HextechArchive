import { useCallback, useEffect, useRef, useState } from "react";
import Frame from "../components/Frame";
import { api } from "../lib/api";

const ACCEPT = ".pdf,.txt,.md,.csv,.docx,.json";
const BADGE = {
  ready: "text-hex border-hex/50",
  processing: "text-gold border-gold/50 glow-pulse",
  error: "text-ember border-ember/50",
};
const LABEL = { ready: "listo", processing: "procesando", error: "error" };

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const input = useRef(null);

  const load = useCallback(() => api("/documents").then(setDocs).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!docs.some((d) => d.status === "processing")) return;
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [docs, load]);

  async function upload(e) {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    setError(""); setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try { await api("/documents", { method: "POST", body: form }); await load(); }
    catch (err) { setError(err.message); }
    finally { setUploading(false); }
  }

  async function remove(id) {
    if (!confirm("¿Eliminar este documento de tu base de conocimiento?")) return;
    try { await api(`/documents/${id}`, { method: "DELETE" }); await load(); }
    catch (err) { setError(err.message); }
  }

  return (
    <Frame className="p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl">Biblioteca de documentos</h2>
        <div>
          <input ref={input} type="file" accept={ACCEPT} className="hidden" onChange={upload} />
          <button className="btn-gold" disabled={uploading} onClick={() => input.current.click()}>
            {uploading ? "Subiendo…" : "Subir documento"}
          </button>
        </div>
      </div>
      <p className="mb-4 text-sm text-ink">Formatos: PDF, TXT, MD, CSV, DOCX, JSON (máx. 10 MB). El agente podrá responder con su contenido.</p>
      {error && <p role="alert" className="mb-3 text-ember">{error}</p>}
      <ul className="divide-y divide-gold/20">
        {docs.length === 0 && <li className="py-6 text-center italic text-ink">Aún no hay documentos.</li>}
        {docs.map((d) => (
          <li key={d.id} className="flex flex-wrap items-center gap-3 py-3">
            <span className="flex-1 break-all">{d.name}</span>
            {d.shared && <span className="rune">corpus base</span>}
            <span className={`rune ${BADGE[d.status]}`}>{LABEL[d.status]}</span>
            {d.status === "error" && <span className="w-full text-sm text-ember">{d.error}</span>}
            {!d.shared && <button className="btn-ghost" onClick={() => remove(d.id)}>Eliminar</button>}
          </li>
        ))}
      </ul>
    </Frame>
  );
}
