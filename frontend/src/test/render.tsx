import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

/** Рендер с React Query и роутером: path — шаблон маршрута, url — текущий адрес. */
export function renderWithProviders(ui: ReactNode, { url = "/", path = "*" }: { url?: string; path?: string } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}><Routes><Route path={path} element={ui} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
}
