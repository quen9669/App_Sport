// Acceptance test of phase 4: the Course page estimates the form from the seed
// runs, predicts race times and gives a pace plan for a target race.
import { expect, test } from '@playwright/test'

import { openTab } from './nav'

test('Course page: form, predictions, and a pace plan for a 10 km', async ({ page }, testInfo) => {
  await page.goto('/')
  await openTab(page, 'Entraînement', 'Course')
  await expect(page.getByRole('heading', { name: 'Ta forme' })).toBeVisible()
  // The seed has regular runs: enough for an estimate.
  await expect(page.getByRole('term').filter({ hasText: 'VDOT' })).toBeVisible()
  const predictions = page.getByRole('table', { name: 'Temps prédits' })
  await expect(predictions.getByRole('row')).toHaveCount(5) // header + 4 distances
  await expect(page.getByRole('table', { name: 'Allures d’entraînement' })).toBeVisible()

  // A target race 8 weeks from now (the same for both devices: one row at most).
  const raceDay = new Date(Date.now() + 56 * 86_400_000).toLocaleDateString('sv-SE', {
    timeZone: 'Europe/Luxembourg',
  })
  const form = page.getByRole('form', { name: 'Préparer une course' })
  await form.getByRole('combobox').selectOption({ label: '10 km' })
  await form.getByLabel('Date').fill(raceDay)
  await form.getByLabel(/Temps visé/).fill('50:00')
  await form.getByRole('button', { name: 'Enregistrer' }).click()

  const plan = page.getByRole('group', { name: 'Plan de course' })
  await expect(plan.getByText(/Dans 8 semaines/)).toBeVisible()
  await expect(plan.getByText(/Ton objectif demande un VDOT de 40/)).toBeVisible()
  const splits = plan.getByRole('table', { name: 'Passages au kilomètre' })
  await expect(splits.getByRole('row')).toHaveCount(11) // header + 10 km
  await expect(splits.getByText('50:00')).toBeVisible()
  if (process.env.E2E_SCREENSHOTS) {
    await page.screenshot({
      path: `${process.env.E2E_SCREENSHOTS}/race-${testInfo.project.name}.png`,
      fullPage: true,
    })
  }
})
