import { expect, test } from "@playwright/test";

test("кандидату 15–17 лет нужна отметка о согласии законного представителя", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel(/E-mail/).fill(`teen${Date.now()}@test.ru`);
  await page.getByLabel(/Пароль/).fill("Secret123");
  await page.getByText(/Даю согласие на обработку персональных данных/).click();
  const submit = page.getByRole("button", { name: "Создать аккаунт" });
  await expect(submit).toBeEnabled();
  await page.getByRole("button", { name: "15–17 лет" }).click();
  await expect(submit).toBeDisabled();
  await page.getByText(/законный представитель дал согласие/).click();
  await expect(submit).toBeEnabled();
});
