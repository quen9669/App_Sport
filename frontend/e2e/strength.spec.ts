// Gym flow: log two sets of squats (the second with "Répéter la série"), save the
// session, and find it in the recent sessions and on the home page.
import { expect, test } from '@playwright/test'

test('log a strength session at the gym', async ({ page }) => {
  await page.goto('/muscu')
  await page.getByLabel('Exercice').selectOption('Squat')
  // Seed data already has squats: the last load is proposed.
  await expect(page.getByLabel('Charge (kg)')).not.toHaveValue('')

  await page.getByRole('button', { name: 'Ajouter la série' }).click()
  await page.getByRole('button', { name: 'Répéter la série' }).click()
  await expect(page.getByRole('heading', { name: '2 séries' })).toBeVisible()

  // The draft survives a reload (phone locked, app closed...).
  await page.reload()
  await expect(page.getByRole('heading', { name: '2 séries' })).toBeVisible()

  await page.getByLabel('Durée (min)').fill('45')
  await page.getByRole('button', { name: 'Terminer la séance' }).click()
  await expect(page.getByText('Séance enregistrée. Bravo !')).toBeVisible()
  await expect(page.getByText(/^Squat : /).first()).toBeVisible() // in "Dernières séances"

  await page.getByRole('link', { name: 'Accueil' }).click()
  await expect(page.getByRole('heading', { name: 'Musculation saisie' })).toBeVisible()
})
