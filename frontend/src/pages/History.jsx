import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Frame from "../components/Frame";
import { api } from "../lib/api";

export default function History() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { api("/conversations").then(setItems).catch((e) => setError(e.message)); }, []);

  return (
    <Frame className="p-6">
      <h2 className="mb-4 text-2xl">Historial de conversaciones</h2>
      {error && <p role="alert" className="text-ember">{error}</p>}
      {items === null && !error && <p className="italic text-ink">Cargando…</p>}
      {items?.length === 0 && <p className="italic text-ink">Aún no has consultado al Archivista.</p>}
      <ul className="divide-y divide-gold/20">
        {items?.map((c) => (
          <li key={c.id}>
            <Link to={`/?c=${c.id}`} className="flex justify-between gap-4 py-3 hover:text-hex">
              <span>{c.title}</span>
              <span className="font-mono text-xs text-ink">{new Date(c.created_at).toLocaleString()}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Frame>
  );
}
