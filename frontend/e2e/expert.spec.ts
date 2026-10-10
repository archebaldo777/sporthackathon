import { expect, test } from "@playwright/test";
import { login, token } from "./helpers";

test("эксперт жюри проходит тест синтетическим профилем Senior за один клик", async ({ page }) => {
  // берём первый свободный аккаунт эксперта: сценарий повторяем на одном стенде до пяти раз
  let email = "", h: Record<string, string> = {}, el: any = null;
  for (let i = 1; i <= 5 && !email; i++) {
    const e = `expert${i}@draft.demo`;
    const hh = { Authorization: `Bearer ${await token(page, e)}` };
    const x = await (await page.request.get("/api/v1/candidate/assessment/eligibility", { headers: hh })).json();
    if (x.survey_required || (x.grades.middle?.allowed && !x.in_progress_attempt_id)) [email, h, el] = [e, hh, x];
  }
  test.skip(!email, "все аккаунты экспертов уже использованы на этом стенде");
  if (el.survey_required)
    await page.request.post("/api/v1/candidate/survey", { headers: h, data: { direction: "development", specialization: "backend", primary_lang: "python",
      stack: ["Python", "PostgreSQL"], experience_years: 3, declared_grade: "middle", work_formats: ["remote"] } });
  const a = await (await page.request.post("/api/v1/candidate/assessment/attempts", { headers: h, data: { target_grade: "middle" } })).json();
  await login(page, email);
  await page.goto(`/c/assessment/test/${a.attempt_id}`);
  await expect(page.getByText(/Режим эксперта/)).toBeVisible();
  await page.getByLabel("Уровень профиля").selectOption("1.5");
  await page.getByRole("button", { name: /Пройти как этот профиль/ }).click();
  await expect(page).toHaveURL(/\/c\/assessment\/result\//);
  await expect(page.getByText("Грейд Middle подтверждён")).toBeVisible(); // профиль θ = 1.5 надёжно выше порога Middle (0)
});
