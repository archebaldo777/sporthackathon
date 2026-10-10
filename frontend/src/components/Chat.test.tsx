import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/test/render";
import { Chat } from "./Chat";

const api = vi.fn();
vi.mock("@/lib/api", () => ({ api: (...a: unknown[]) => api(...a), ApiError: class extends Error {} }));

describe("переписка в приглашении", () => {
  beforeEach(() => api.mockReset());

  it("показывает свои и чужие сообщения и отметку о прочтении", async () => {
    api.mockResolvedValue({ items: [
      { id: 1, from: "employer", mine: false, text: "Удобно в четверг?", created_at: "2026-10-07T10:00:00Z", read: true },
      { id: 2, from: "candidate", mine: true, text: "Да, после 15:00", created_at: "2026-10-07T10:05:00Z", read: true },
    ] });
    renderWithProviders(<Chat base="/candidate/invitations/3" counterpart="«ТехноВектор»" />);
    expect(await screen.findByText("Удобно в четверг?")).toBeInTheDocument();
    expect(screen.getByText("Да, после 15:00")).toBeInTheDocument();
    expect(screen.getByText(/прочитано/)).toBeInTheDocument();
    expect(api).toHaveBeenCalledWith("/candidate/invitations/3/messages");
  });

  it("не отправляет пустое сообщение и отправляет непустое", async () => {
    api.mockResolvedValue({ items: [] });
    renderWithProviders(<Chat base="/employer/invitations/7" counterpart="кандидатом K-1" />);
    const send = await screen.findByRole("button", { name: /отправить/i });
    expect(send).toBeDisabled();
    await userEvent.type(screen.getByPlaceholderText("Сообщение…"), "Ссылка на встречу");
    expect(send).toBeEnabled();
    await userEvent.click(send);
    await waitFor(() => expect(api).toHaveBeenCalledWith("/employer/invitations/7/messages", { body: { text: "Ссылка на встречу" } }));
  });
});
