import { expect, test } from "@playwright/test";
import { login, token } from "./helpers";

test("кандидат переписывается с работодателем после принятия приглашения", async ({ page }) => {
  const t = await token(page, "candidate@draft.demo");
  const list = await (await page.request.get("/api/v1/candidate/invitations", { headers: { Authorization: `Bearer ${t}` } })).json();
  const accepted = list.items.find((i: any) => i.status === "accepted");
  test.skip(!accepted, "в демо-данных нет принятого приглашения");
  await login(page, "candidate@draft.demo");
  await page.goto(`/c/invitations/${accepted.id}`);
  await expect(page.getByText(/Переписка с «/)).toBeVisible();
  const text = `Проверка связи ${Date.now()}`;
  await page.getByPlaceholder("Сообщение…").fill(text);
  await page.getByRole("button", { name: "Отправить" }).click();
  await expect(page.getByText(text)).toBeVisible();
  await expect(page.getByRole("button", { name: /доступ к контактам|Снова открыть контакты/ })).toBeVisible();
});

test("кандидат видит зарплатный радар и путь роста", async ({ page }) => {
  await login(page, "candidate@draft.demo");
  await page.goto("/c/growth");
  await expect(page.getByText("Зарплатный радар")).toBeVisible();
  await expect(page.getByText("Следующие шаги")).toBeVisible();
});

test("несколько категорий: кандидат видит дополнительную, работодатель находит его по ней", async ({ page }) => {
  await login(page, "candidate@draft.demo");
  await page.goto("/c/assessment");
  await expect(page.getByRole("heading", { name: "Мои категории" })).toBeVisible();
  await expect(page.getByText("DevOps · Junior")).toBeVisible();
  const t = await token(page, "employer@draft.demo");
  const found = await (await page.request.get("/api/v1/employer/candidates?specialization=devops&limit=100",
                                              { headers: { Authorization: `Bearer ${t}` } })).json();
  expect(found.items.some((c: any) => c.matched_additional && c.categories.length > 1)).toBeTruthy();
});
