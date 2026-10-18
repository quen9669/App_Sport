// Acceptance test of phase 3a: the Santé page shows sleep, recovery and training
// load and intensity minutes from the synthetic data of the seed script (21 days).
import { expect, test } from '@playwright/test'

test('Santé page: sleep and recovery curves, then the training load', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Santé' }).click()

  await expect(page.getByRole('heading', { name: 'Sommeil' })).toBeVisible()
  await expect(page.getByText('Durée moyenne')).toBeVisible()
  await expect(page.getByText(/^Horaires : coucher /)).toBeVisible()
  // Sleep, resting HR and HRV charts are drawn from the seed nights.
  await expect(page.locator('.recharts-surface')).not.toHaveCount(0)

  await page.getByRole('button', { name: '7 jours' }).click()
  await expect(page.getByRole('button', { name: '7 jours' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(page.getByText(/sur [1-7] nuits\.$/)).toBeVisible()

  await expect(page.getByRole('heading', { name: 'Charge d’entraînement' })).toBeVisible()
  await expect(page.getByText(/pas un diagnostic/)).toBeVisible()

  // Intensity minutes: the seed has some every day, and no goal yet.
  const intensity = page.getByRole('region', { name: 'Minutes d’intensité' })
  await expect(intensity.locator('.recharts-surface')).toBeVisible()
  await expect(intensity.getByRole('link', { name: /Ajoute un objectif/ })).toBeVisible()
})

test('Santé page: write a day with a cigarette, then remove it', async ({ page }, testInfo) => {
  // Each device writes its own day: the two projects share the E2E database.
  const daysAgo = testInfo.project.name === 'android' ? 4 : 3
  const day = new Date(Date.now() - daysAgo * 86_400_000).toLocaleDateString('sv-SE', {
    timeZone: 'Europe/Luxembourg',
  })
  await page.goto('/sante')

  const card = page.getByRole('region', { name: 'Sans cigarette' })
  await expect(card.getByText('Jours sans cigarette', { exact: true })).toBeVisible()
  await card.getByRole('button', { name: '+ J’ai fumé' }).click()
  await card.getByLabel('Jour').fill(day)
  await card.getByLabel('Note (facultatif)').fill('test E2E')
  await card.getByRole('button', { name: 'Enregistrer', exact: true }).click()

  const entry = card.getByRole('listitem').filter({ hasText: 'test E2E' })
  await expect(entry).toBeVisible()
  if (process.env.E2E_SCREENSHOTS) {
    await card.screenshot({
      path: `${process.env.E2E_SCREENSHOTS}/smoke-${testInfo.project.name}.png`,
    })
  }
  await entry.getByRole('button', { name: /Supprimer/ }).click()
  await expect(entry).toHaveCount(0)
})
