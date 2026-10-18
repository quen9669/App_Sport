// End-to-end smoke test: opens the real app in Chromium, with the real backend
// running, and checks the main page loads and reaches the API.
import { expect, test } from '@playwright/test'

test('home page loads and reaches the backend', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'App Sport' })).toBeVisible()
  await expect(page.getByRole('status')).toHaveText('Backend OK')
})
