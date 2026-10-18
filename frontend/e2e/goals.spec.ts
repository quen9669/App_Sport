// Acceptance test of phase 2: define "3 strength + 3 cardio" and see the week fill up
// with the synthetic activities created by the seed script.
import { expect, test } from '@playwright/test'

const API = 'http://localhost:8000'

// Tests share one database: start each one without goals.
test.beforeEach(async ({ request }) => {
  const goals = (await (await request.get(`${API}/api/goals`)).json()) as { id: number }[]
  for (const goal of goals) await request.delete(`${API}/api/goals/${goal.id}`)
})

test('define 3 strength + 3 cardio and see the rings on the home page', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Définis tes objectifs' })).toBeVisible()

  await page.getByRole('link', { name: 'Objectifs', exact: true }).click()
  await page.getByRole('button', { name: '3 muscu + 3 cardio par semaine' }).click()
  await expect(page.getByRole('list')).toContainText('Séances de musculation : 3 séances')

  await page.getByRole('link', { name: 'Accueil' }).click()
  await expect(page.getByLabel(/^Séances de musculation : .* sur 3 séances$/)).toBeVisible()
  await expect(page.getByLabel(/^Séances de cardio : .* sur 3 séances$/)).toBeVisible()

  // The previous week is complete in the seed data: it has sessions.
  await page.getByRole('button', { name: 'Semaine précédente' }).click()
  await expect(page.getByRole('combobox', { name: /^Catégorie de / }).first()).toBeVisible()
})

test('quick weigh-in from the home page', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: '+ Poids' }).click()
  await page.getByRole('button', { name: 'Plus 0,1 kg' }).click()
  await page.getByRole('button', { name: 'Enregistrer' }).click()
  await expect(page.getByText(/kg enregistrés$/)).toBeVisible()

  await page.getByRole('link', { name: 'Voir la courbe et mon profil' }).click()
  await expect(page.getByRole('heading', { name: 'Courbe de poids' })).toBeVisible()
  await expect(page.locator('.recharts-surface').first()).toBeVisible()
})
