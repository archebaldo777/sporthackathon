import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import Growth from "./Growth";

let payload: any;
vi.mock("@/lib/api", () => ({ api: async () => payload }));

describe("рост и зарплаты", () => {
  it("радар, разрыв навыков и шаги", async () => {
    payload = {
      available: true, category: "Backend · Middle", grade_confirmed: true, own_expectation: 290000, position: "in", reference_median: 275000,
      now: { market_median: 250000, expectations: { p25: 220000, p50: 250000, p75: 295000, n: 61 }, vacancies: null, offers: { median: 275000, n: 11, companies: 4 } },
      next_grade: "senior", next: { market_median: 400000, expectations: null, vacancies: null, offers: null },
      demand: { grade: "senior", postings: 3, gaps: [{ skill: "Docker", share: 0.67 }], strengths: [{ skill: "Python", share: 0.33, verified: true }] },
      steps: ["Свяжите ФСП ID"], privacy: { min_values: 5, min_companies: 3 },
    };
    renderWithProviders(<Growth />);
    expect(await screen.findByText("Зарплатный радар")).toBeInTheDocument();
    expect(screen.getByText(/в рынке категории/)).toBeInTheDocument();
    expect(screen.getByText(/ожидания 61 кандидатов/)).toBeInTheDocument();
    expect(screen.getByText("Docker")).toBeInTheDocument();
    expect(screen.getByText(/выборка пока мала/)).toBeInTheDocument();
    expect(screen.getByText("Свяжите ФСП ID")).toBeInTheDocument();
  });

  it("без категории — подсказка пройти опрос", async () => {
    payload = { available: false, reason: "Пройдите опрос и выберите грейд" };
    renderWithProviders(<Growth />);
    expect(await screen.findByText(/Пройдите опрос/)).toBeInTheDocument();
  });
});
