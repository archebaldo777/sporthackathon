import { defineConfig } from "@playwright/test";

// Браузерные сценарии против запущенного стенда: локально — dev-сервер, в CI — docker compose (порт 8080)
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    channel: process.env.CI ? undefined : "chrome",
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
});
