import { expect, type Page } from "@playwright/test";

export const PASSWORD = "Demo2026!";

export async function login(page: Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Пароль").fill(PASSWORD);
  await page.locator("form").getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

/** Токен для подготовки данных через API (то же, что сделал бы пользователь в интерфейсе). */
export async function token(page: Page, email: string): Promise<string> {
  const r = await page.request.post("/api/v1/auth/login", { data: { email, password: PASSWORD } });
  expect(r.ok()).toBeTruthy();
  return (await r.json()).access_token;
}
