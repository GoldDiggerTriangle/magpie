import originalText from "../../../../SPRINT25_EVIDENCE.md?raw";
import mappedText from "../../../../SPRINT26_CONTROL_INVENTORY.md?raw";
import { expect, test } from "vitest";

test("the complete original 76-row inventory remains intact with a tab and tap path for every control", () => {
  const original = [...originalText.matchAll(/^\| \[x\] ([ABQDS]\d{2}) \| ([^\n]+?) \|/gm)].map(m => [m[1], m[2]]);
  const mapped = [...mappedText.matchAll(/^\| \[x\] ([ABQDS]\d{2}) \| ([^\n]+?) \| ([^\n]+?) \| ([^\n]+?) \|/gm)];
  expect(original).toHaveLength(76);
  expect(mapped.map(m => [m[1], m[2]])).toEqual(original);
  expect(new Set(mapped.map(m => m[1])).size).toBe(76);
  for (const row of mapped) {
    expect(row[3].trim().length).toBeGreaterThan(0);
    expect(row[4].trim().length).toBeGreaterThan(0);
  }
});
