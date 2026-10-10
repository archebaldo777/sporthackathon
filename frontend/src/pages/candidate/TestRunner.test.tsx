import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import TestRunner from "./TestRunner";

let expertMode = false;
const item = { item_id: 5, position: 1, max_items: 22, competency: "Базы данных", kind: "single", text: "Что вернёт запрос?", options: ["1", "2"], time_left_s: 120 };
vi.mock("@/lib/api", () => ({
  api: async (path: string) => (path === "/candidate/me" ? { expert_mode: expertMode } : { finished: false, item }),
  ApiError: class extends Error {},
}));

describe("страница теста", () => {
  it("обычному кандидату режим эксперта не показывается", async () => {
    expertMode = false;
    renderWithProviders(<TestRunner />, { url: "/c/assessment/test/9", path: "/c/assessment/test/:id" });
    expect(await screen.findByText("Что вернёт запрос?")).toBeInTheDocument();
    expect(screen.queryByText(/Режим эксперта/)).not.toBeInTheDocument();
  });

  it("демо-аккаунту жюри — кнопки ответа и автопрохождения", async () => {
    expertMode = true;
    renderWithProviders(<TestRunner />, { url: "/c/assessment/test/9", path: "/c/assessment/test/:id" });
    expect(await screen.findByText(/Режим эксперта/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ответить верно" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Пройти как этот профиль/ })).toBeInTheDocument();
  });
});
