export function parseSSE(buffer) {
  const parts = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = parts.pop() ?? "";
  const events = [];
  for (const p of parts) {
    if (!p.startsWith("data: ")) continue;
    try {
      events.push(JSON.parse(p.slice(6)));
    } catch {
      // skip malformed block
    }
  }
  return { events, rest };
}
