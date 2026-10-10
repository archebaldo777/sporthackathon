import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("работодатель сравнивает кандидатов в подборке и видит, почему один выше другого", async ({ page }) => {
  await login(page, "employer@draft.demo");
  await page.goto("/e/needs/1");
  const boxes = page.getByRole("checkbox", { name: "Выбрать" });
  await expect(boxes.first()).toBeVisible();
  await boxes.nth(0).check();
  await boxes.nth(1).check();
  await page.getByRole("button", { name: "Сравнить" }).click();
  await expect(page.getByText("Сравнение кандидатов")).toBeVisible();
  await expect(page.getByText(/Почему «.+» выше «.+»/)).toBeVisible();
  await expect(page.getByText("1-е место")).toBeVisible();
});

test("суммы в подборке подписаны как gross", async ({ page }) => {
  await login(page, "employer@draft.demo");
  await page.goto("/e/needs/1");
  await expect(page.getByText(/тыс\. ₽ gross/).first()).toBeVisible();
});
