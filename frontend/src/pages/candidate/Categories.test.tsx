import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import { Categories } from "./Assessment";

const api = vi.fn();
vi.mock("@/lib/api", () => ({ api: (...a: unknown[]) => api(...a), ApiError: class extends Error {} }));

const catalog = {
  specializations: [
    { code: "backend", name: "Backend-разработка", short: "Backend", direction: "development", langs: ["python"], frameworks: [], blueprint: {}, core_skills: [] },
    { code: "devops", name: "DevOps / SRE", short: "DevOps", direction: "infra", langs: ["python"], frameworks: [], blueprint: {}, core_skills: [] },
    { code: "qa", name: "QA / Тестирование", short: "QA", direction: "quality", langs: ["python"], frameworks: [], blueprint: {}, core_skills: [] },
  ],
  grades: [{ code: "junior", name: "Junior", order: 1, years: "1–2" }, { code: "middle", name: "Middle", order: 2, years: "2–5" }],
};
const items = [
  { specialization: "backend", label: "Backend · Middle", confirmed: true, main: true, grade: "middle" },
  { specialization: "devops", label: "DevOps · Junior", confirmed: false, main: false, declared_grade: "junior" },
];

describe("несколько категорий кандидата", () => {
  beforeEach(() => {
    api.mockReset();
    api.mockImplementation(async (path: string) => (path === "/catalog" ? catalog : { items, max_extra: 2 }));
  });

  it("показывает основную и дополнительную категории со статусами", async () => {
    renderWithProviders(<Categories busy={false} />);
    expect(await screen.findByText("Backend · Middle")).toBeInTheDocument();
    expect(screen.getByText("DevOps · Junior")).toBeInTheDocument();
    expect(screen.getByText("основная")).toBeInTheDocument();
    expect(screen.getByText("не подтверждён")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Пройти тест" })).toBeEnabled();
  });

  it("делает дополнительную категорию основной и добавляет новую только из незанятых специализаций", async () => {
    renderWithProviders(<Categories busy={false} />);
    await userEvent.click(await screen.findByRole("button", { name: "Пройти тест" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/candidate/categories/devops/main", { method: "POST" }));
    await userEvent.click(screen.getByRole("button", { name: /Добавить категорию/ }));
    const spec = screen.getByLabelText("Специализация");
    expect([...spec.querySelectorAll("option")].map((o) => o.getAttribute("value"))).toEqual(["", "qa"]);
    await userEvent.selectOptions(spec, "qa");
    await userEvent.selectOptions(screen.getByLabelText("Грейд"), "junior");
    await userEvent.click(screen.getByRole("button", { name: "Добавить" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("/candidate/categories", { body: { specialization: "qa", declared_grade: "junior" } }));
  });

  it("во время начатого теста сменить основную нельзя", async () => {
    renderWithProviders(<Categories busy />);
    expect(await screen.findByRole("button", { name: "Пройти тест" })).toBeDisabled();
    expect(screen.getByText(/после завершения начатого теста/)).toBeInTheDocument();
  });
});
