import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import { CompareModal } from "./Compare";

const comps = (l: number, s: number) => [
  { key: "L", name: "Подтверждённый уровень", value: l / 30, weight: 0.39, contribution: l },
  { key: "S", name: "Навыки", value: s / 20, weight: 0.2, contribution: s },
];
const card = (id: number, name: string, score: number, l: number, s: number) => ({
  id, name, category: "Backend · Middle", salary_from: 250000, salary_to: 300000, fsp: { count: id === 1 ? 2 : 0 }, contacts_revealed: false,
  match: { score, components: comps(l, s), skills: { Python: { evidence: "test", must: true } }, acceptance: { p: 0.6, label: "высокая" } },
});
vi.mock("@/lib/api", () => ({
  api: async () => ({
    need: { id: 1, salary_to: 320000, must_skills: ["Python"], nice_skills: [] },
    skills: ["Python"],
    items: [card(1, "Анна", 80, 28, 15), card(2, "Борис", 74, 22, 16)],
    pairs: [{ a: 1, b: 2, a_name: "Анна", b_name: "Борис", score_gap: 6,
      a_better: [{ key: "L", name: "Подтверждённый уровень", points: 6 }], b_better: [{ key: "S", name: "Навыки", points: 1 }],
      a_modifiers: [], b_modifiers: ["ожидания выше бюджета (оценка ×0.62)"] }],
  }),
}));

describe("сравнение кандидатов", () => {
  it("показывает места, вклад компонент и объяснение разницы", async () => {
    renderWithProviders(<CompareModal needId={1} ids={[1, 2]} onClose={() => {}} />);
    expect(await screen.findByText("1-е место")).toBeInTheDocument();
    expect(screen.getByText(/Почему «Анна» выше «Борис»/)).toBeInTheDocument();
    expect(screen.getAllByText("+6").length).toBe(2); // разрыв в баллах и вклад уровня
    expect(screen.getByText(/ожидания выше бюджета/)).toBeInTheDocument();
    expect(screen.getByText("нет истории — без штрафа")).toBeInTheDocument();
  });

  it("закрыто, пока не выбрано хотя бы два кандидата", () => {
    renderWithProviders(<CompareModal needId={1} ids={[1]} onClose={() => {}} />);
    expect(screen.queryByText("Сравнение кандидатов")).not.toBeInTheDocument();
  });
});
