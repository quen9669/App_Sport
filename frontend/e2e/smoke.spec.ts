// End-to-end tests: open the real app in Chromium, with the real backend
// running, and check the main pages load and reach the API.
import { expect, test } from '@playwright/test'

test('home page loads and reaches the backend', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'App Sport' })).toBeVisible()
  await expect(page.getByRole('status')).toHaveText('Backend OK')
})

test('sources page shows every data source and the sync journal', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Sources' }).click()

  await expect(page.getByRole('heading', { name: 'Sources de données' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Strava' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Garmin' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Historique des synchronisations' })).toBeVisible()
})
