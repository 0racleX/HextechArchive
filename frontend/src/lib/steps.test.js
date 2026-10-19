import { describe, expect, it } from "vitest";
import { DEFAULT_STEP_LABEL, stepLabel } from "./steps.js";

describe("stepLabel", () => {
  it("maps known graph nodes to Spanish labels", () => {
    expect(stepLabel("validate_intent")).toBe("Entendiendo la pregunta");
    expect(stepLabel("retrieve")).toBe("Buscando en el archivo");
    expect(stepLabel("grade_context")).toBe("Verificando el contexto");
    expect(stepLabel("generate")).toBe("Redactando respuesta");
  });

  it("falls back for unknown or missing nodes", () => {
    expect(stepLabel("nope")).toBe(DEFAULT_STEP_LABEL);
    expect(stepLabel(undefined)).toBe(DEFAULT_STEP_LABEL);
  });
});
