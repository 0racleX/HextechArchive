export function parseSSE(buffer) {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events = parts
    .filter((p) => p.startsWith("data: "))
    .map((p) => JSON.parse(p.slice(6)));
  return { events, rest };
}
