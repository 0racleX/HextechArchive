import { describe, expect, it } from "vitest";
import { parseSSE } from "./sse.js";

describe("parseSSE", () => {
  it("parses complete events and keeps the incomplete remainder", () => {
    const buf = 'data: {"type":"token","text":"Ho"}\n\ndata: {"type":"token","text":"la"}\n\ndata: {"type":"fi';
    const { events, rest } = parseSSE(buf);
    expect(events).toEqual([
      { type: "token", text: "Ho" },
      { type: "token", text: "la" },
    ]);
    expect(rest).toBe('data: {"type":"fi');
  });

  it("returns nothing for an empty buffer", () => {
    expect(parseSSE("")).toEqual({ events: [], rest: "" });
  });

  it("ignores non-data blocks", () => {
    const { events } = parseSSE(': keep-alive\n\ndata: {"type":"step","node":"retrieve"}\n\n');
    expect(events).toEqual([{ type: "step", node: "retrieve" }]);
  });

  it("ignores ': ping' heartbeat blocks between events", () => {
    const { events, rest } = parseSSE(': ping\n\ndata: {"type":"token","text":"a"}\n\n: ping\n\n');
    expect(events).toEqual([{ type: "token", text: "a" }]);
    expect(rest).toBe("");
  });

  it("parses CRLF-delimited events", () => {
    const { events, rest } = parseSSE('data: {"type":"token","text":"a"}\r\n\r\ndata: {"type":"fi');
    expect(events).toEqual([{ type: "token", text: "a" }]);
    expect(rest).toBe('data: {"type":"fi');
  });

  it("skips malformed data blocks instead of throwing", () => {
    const { events } = parseSSE('data: {bad\n\ndata: {"type":"done"}\n\n');
    expect(events).toEqual([{ type: "done" }]);
  });
});
