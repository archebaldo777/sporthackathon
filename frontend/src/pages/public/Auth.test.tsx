import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import Auth from "./Auth";

vi.mock("@/lib/api", () => ({ api: vi.fn(), ApiError: class extends Error {} }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ login: vi.fn(), acceptTokens: vi.fn(), user: null }), homeFor: () => "/" }));

describe("регистрация кандидата 15–17 лет", () => {
  it("без согласия законного представителя аккаунт не создать", async () => {
    renderWithProviders(<Auth mode="register" />);
    await userEvent.type(screen.getByLabelText(/E-mail/), "teen@test.ru");
    await userEvent.type(screen.getByLabelText(/Пароль/), "Secret123");
    await userEvent.click(screen.getByText(/Даю согласие на обработку персональных данных/));
    const submit = screen.getByRole("button", { name: "Создать аккаунт" });
    expect(submit).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "15–17 лет" }));
    expect(submit).toBeDisabled();
    await userEvent.click(screen.getByText(/законный представитель дал согласие/));
    expect(submit).toBeEnabled();
    expect(screen.getByText(/только лёгкий труд/)).toBeInTheDocument();
  });
});
