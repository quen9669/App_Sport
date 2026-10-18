// End-to-end tests: open the real app in Chromium, with the real backend
// running, and check the main pages load and reach the API.
import { expect, test } from '@playwright/test'

import { openTab } from './nav'

test('home page loads and reaches the backend', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Ma semaine', level: 1 })).toBeVisible()
  await expect(page.getByRole('heading', { name: /^Semaine du / })).toBeVisible()
  // The backend answers: no "Backend injoignable" banner.
  await expect(page.getByText(/Backend injoignable/)).toHaveCount(0)
})

test('sources page shows every data source and the sync journal', async ({ page }) => {
  await page.goto('/')
  await openTab(page, 'Réglages', 'Sources')

  await expect(page.getByRole('heading', { name: 'Sources de données' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Strava' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Garmin' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Historique des synchronisations' })).toBeVisible()
})
