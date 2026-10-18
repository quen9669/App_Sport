// Acceptance test of phase 3b: open the map with the synthetic activities,
// filter it, then open the detail of one activity (map + charts).
import { expect, test } from '@playwright/test'

// No external requests in tests: the OpenStreetMap tiles are answered with an
// empty response (the map just has no background).
test.beforeEach(async ({ page }) => {
  await page.route('https://tile.openstreetmap.org/**', (route) =>
    route.fulfill({ status: 204, body: '' }),
  )
})

test('map: routes, filters, heatmap, then the detail of an activity', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Carte' }).click()

  await expect(page.getByRole('heading', { name: 'Carte' })).toBeVisible()
  // Leaflet draws the routes on a canvas inside the map.
  await expect(page.locator('.leaflet-container canvas')).toBeVisible()
  const summary = page.getByText(/correspond.* aux filtres/)
  await expect(summary).toBeVisible()
  // The gym sessions without GPS are on their default place.
  await expect(page.getByRole('region', { name: 'Dans la zone affichée' })).toContainText(
    'Jims Gare',
  )

  await page.getByRole('group', { name: 'Sport' }).getByRole('button', { name: 'Vélo' }).click()
  await expect(page.getByRole('region', { name: 'Dans la zone affichée' })).not.toContainText(
    'Jims Gare',
  )
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

test('places: a gym session shows its place and it can be changed', async ({ page }) => {
  await page.goto('/carte')
  const panel = page.getByRole('region', { name: 'Mes lieux' })
  await expect(panel.getByRole('form', { name: 'Lieu Jims Gasperich' })).toBeVisible()
  await expect(panel.getByRole('form', { name: 'Lieu Jims Gare' })).toBeVisible()
})
