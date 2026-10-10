import { describe, expect, it } from "vitest";
import { GROSS_HINT, plural, salaryRange } from "./format";

describe("суммы подписаны как gross", () => {
  it("вилка и границы", () => {
    expect(salaryRange(200000, 280000)).toBe("200–280 тыс. ₽ gross");
    expect(salaryRange(150000, null)).toBe("от 150 тыс. ₽ gross");
    expect(salaryRange(null, 90000)).toBe("до 90 тыс. ₽ gross");
    expect(salaryRange(null, null)).toBe("не указана");
    expect(GROSS_HINT).toContain("НДФЛ");
  });
  it("склонение", () => {
    expect(plural(1, "задание", "задания", "заданий")).toBe("задание");
    expect(plural(3, "задание", "задания", "заданий")).toBe("задания");
    expect(plural(11, "задание", "задания", "заданий")).toBe("заданий");
  });
});
