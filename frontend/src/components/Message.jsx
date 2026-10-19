export default function Message({ role, content, sources = [], refused = false, pending = false, stepText = "" }) {
  const mine = role === "user";
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] border px-4 py-3 ${
          mine
            ? "border-hex/40 bg-hex/10"
            : refused
              ? "border-ember/50 bg-ember/10"
              : "border-gold/40 bg-panel"
        } ${pending ? "glow-pulse" : ""}`}
      >
        {!mine && <div className="mb-1 font-display text-[0.65rem] tracking-[0.25em] text-gold">ARCHIVISTA</div>}
        <p className="whitespace-pre-wrap" role={pending && !content ? "status" : undefined}>{content || (pending ? `${stepText || "Consultando los archivos"}…` : "")}</p>
        {!mine && !refused && sources.length > 0 && (
          <details className="mt-3">
            <summary className="cursor-pointer text-sm text-ink hover:text-gold">
              Fuentes consultadas ({sources.length})
            </summary>
            <ul className="mt-2 space-y-2">
              {sources.map((s, i) => (
                <li key={i} className="border-l-2 border-hex/50 pl-3 text-sm">
                  <span className="rune">[{i + 1}] {s.document}</span>
                  <span className="rune ml-2">sim {s.score}</span>
                  <p className="mt-1 italic text-ink">“{s.snippet}…”</p>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  );
}
