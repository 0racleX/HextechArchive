import { describe, expect, it } from "vitest";
import { normalizeBase } from "./baseUrl.js";

describe("normalizeBase", () => {
  it("strips trailing slashes", () => {
    expect(normalizeBase("https://x.hf.space/")).toBe("https://x.hf.space");
    expect(normalizeBase("https://x.hf.space///")).toBe("https://x.hf.space");
  });
  it("keeps clean urls and tolerates undefined", () => {
    expect(normalizeBase("http://localhost:8000")).toBe("http://localhost:8000");
    expect(normalizeBase(undefined)).toBe("");
  });
});
