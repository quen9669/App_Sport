// Playwright configuration for end-to-end tests (e2e/).
// `webServer` starts the backend and the frontend automatically before the tests.
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  // In CI, retry once to absorb rare timing hiccups; locally, fail fast.
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    // Optional: use an already-installed Chromium instead of Playwright's own download.
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH || undefined },
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    // Mobile-first app: also check it on an Android phone viewport.
    { name: 'android', use: { ...devices['Pixel 7'] } },
  ],
  webServer: [
    {
      // A separate database for E2E tests, created from the migrations, without scheduler.
      command: 'uv run alembic upgrade head && uv run uvicorn app.main:app --port 8000',
      cwd: '../backend',
      env: { DATABASE_URL: 'sqlite:///./data/e2e.db', SCHEDULER_ENABLED: 'false' },
      url: 'http://localhost:8000/api/health',
      reuseExistingServer: !process.env.CI,
    },
    {
      command: 'npm run dev -- --port 5173 --strictPort',
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
    },
  ],
})
