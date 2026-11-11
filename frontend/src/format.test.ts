import { describe, expect, it } from "vitest";
import { formatDuration, formatMiles, riskColor, riskLabel, toLocalInputValue } from "./format";

describe("formatDuration", () => {
  it("shows minutes alone under an hour", () => {
    expect(formatDuration(45 * 60)).toBe("45 min");
  });

  it("shows hours and minutes", () => {
    expect(formatDuration(14 * 3600 + 5 * 60)).toBe("14 h 5 min");
  });

  it("rolls rounded minutes into the hour", () => {
    expect(formatDuration(3599.9)).toBe("1 h 0 min");
  });
});

describe("formatMiles", () => {
  it("rounds to whole miles", () => {
    expect(formatMiles(12.6)).toBe("13 mi");
  });
});

describe("risk display", () => {
  it("never shows missing data as a risk level", () => {
    expect(riskLabel(null)).toBe("No data");
    expect(riskColor(null)).not.toBe(riskColor("low"));
  });

  it("labels No Travel", () => {
    expect(riskLabel("no_travel")).toBe("No Travel");
  });
});

describe("toLocalInputValue", () => {
  it("round trips through the Date a datetime-local input produces", () => {
    const date = new Date(2026, 10, 10, 8, 30);
    expect(new Date(toLocalInputValue(date)).getTime()).toBe(date.getTime());
  });
});
