// Acceptance test of phase 3b: open the map with the synthetic activities,
// filter it, then open the detail of one activity (map + charts).
import { expect, test } from '@playwright/test'

import { openTab } from './nav'

// No external requests in tests: the OpenStreetMap tiles are answered with an
// empty response (the map just has no background).
test.beforeEach(async ({ page }) => {
  await page.route('https://tile.openstreetmap.org/**', (route) =>
    route.fulfill({ status: 204, body: '' }),
  )
})

test('map: routes, filters, heatmap, then the detail of an activity', async ({ page }) => {
  await page.goto('/')
  await openTab(page, 'Entraînement', 'Activités')

  await expect(page.getByRole('heading', { name: 'Activités', level: 1 })).toBeVisible()
  // Leaflet draws the routes on a canvas inside the map.
  await expect(page.locator('.leaflet-container canvas')).toBeVisible()
  const summary = page.getByText(/correspond.* aux filtres/)
  await expect(summary).toBeVisible()
  // The last 14 days by default, one activity per table row, gym sessions included
  // (they are placed at their gym, in Luxembourg).
  const list = page.getByRole('region', { name: 'Dans la zone affichée' })
  await expect(page.getByRole('button', { name: '14 jours' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(list.getByRole('table')).toContainText('Muscu')
  await expect(list.getByRole('table')).toContainText('Luxembourg')
  if (process.env.E2E_SCREENSHOTS) {
    await page.screenshot({
      path: `${process.env.E2E_SCREENSHOTS}/map-${test.info().project.name}.png`,
      fullPage: true,
    })
  }

  await page.getByRole('group', { name: 'Sport' }).getByRole('button', { name: 'Vélo' }).click()
  await expect(list.getByRole('table')).not.toContainText('Muscu')
  await page.getByRole('button', { name: 'Heatmap' }).click()
  await expect(page.getByRole('button', { name: 'Heatmap' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )

  await page.getByRole('group', { name: 'Sport' }).getByRole('button', { name: 'Course' }).click()
  await page
    .getByRole('region', { name: 'Dans la zone affichée' })
    .getByRole('link')
    .first()
    .click()

  await expect(page).toHaveURL(/\/activites\/\d+$/)
  await expect(page.getByText('Allure moy.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Profil d’altitude' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Fréquence cardiaque' })).toBeVisible()
  await expect(page.locator('.leaflet-container canvas')).toBeVisible()
})

test('places: the gyms are listed in Mes lieux', async ({ page }) => {
  await page.goto('/')
  await openTab(page, 'Réglages', 'Mes lieux')
  const panel = page.getByRole('region', { name: 'Mes lieux' })
  await expect(panel.getByRole('form', { name: 'Lieu Jims Gasperich' })).toBeVisible()
  await expect(panel.getByRole('form', { name: 'Lieu Jims Gare' })).toBeVisible()
})
