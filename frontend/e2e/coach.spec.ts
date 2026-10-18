// Acceptance test of phase 5a (screen side): the coach page in a real browser.
// E2E has no API key: the real backend says the coach waits for it. The second
// test replaces the coach's answer with a recorded stream, to check that the
// browser shows it piece by piece (the engine itself is tested in pytest).
import { expect, test } from '@playwright/test'

test('Coach page: waits for the API key, memories can be added', async ({ page }, testInfo) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Coach' }).click()
  await expect(page.getByRole('heading', { name: 'Coach muscu et cardio' })).toBeVisible()
  await expect(page.getByText(/attend ta clé API Gemini/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Envoyer' })).toBeDisabled()

  const panel = page.getByRole('region', { name: 'Ce que le coach retient' })
  const text = `Pas de course le lundi (${testInfo.project.name})`
  await panel.getByLabel('À retenir').fill(text)
  await panel.getByRole('button', { name: 'Ajouter' }).click()
  const forget = panel.getByRole('button', { name: `Oublier « ${text} »` })
  await expect(forget).toBeVisible()
  await forget.click()
  await expect(forget).toHaveCount(0)
})

test('Coach page: a streamed answer appears in the chat', async ({ page }, testInfo) => {
  await page.route('**/api/coach/status', (route) =>
    route.fulfill({
      json: {
        configured: true,
        model: 'gemini-3.8-flash',
        budget: {
          month: '2026-10',
          spent_eur: 0.42,
          limit_eur: 10,
          warning: false,
          exhausted: false,
        },
      },
    }),
  )
  const events = [
    ['tool', { name: 'get_race_predictions', label: 'regarde tes prédictions de course' }],
    ['tool', { name: 'get_recovery_metrics', label: 'lit ta récupération' }],
    [
      'text',
      {
        text:
          'Ta préparation est **en bonne voie** : la prédiction est de 49:40 pour un objectif ' +
          'de 50:00.\n- Garde 2 sorties faciles par semaine\n- Ajoute une séance au seuil (5:00 /km)',
      },
    ],
    ['done', { cost_eur: 0.03, month_spent_eur: 0.45, month_limit_eur: 10 }],
  ]
  await page.route('**/api/coach/conversations/*/messages', (route) =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: events.map(([n, d]) => `event: ${n}\ndata: ${JSON.stringify(d)}\n\n`).join(''),
    }),
  )
  await page.goto('/coach')
  await page.getByRole('button', { name: 'Nouvelle', exact: true }).click()
  await page.getByRole('button', { name: /préparation du 10 km/ }).click()

  const chat = page.getByRole('region', { name: 'Conversation avec le coach' })
  await expect(chat.getByText('en bonne voie')).toBeVisible()
  await expect(chat.getByText('lit ta récupération')).toBeVisible()
  await expect(chat.getByText('Ajoute une séance au seuil (5:00 /km)')).toBeVisible()
  await expect(page.getByText(/Ce mois-ci : 0,45 €/)).toBeVisible()
  if (process.env.E2E_SCREENSHOTS) {
    await page.screenshot({
      path: `${process.env.E2E_SCREENSHOTS}/coach-${testInfo.project.name}.png`,
      fullPage: true,
    })
  }
})

test('Coach page: a weekly plan is accepted, then shown on Accueil', async ({ page }, testInfo) => {
  const monday = '2026-10-19'
  const plan = {
    id: 901,
    coach: 'training',
    week_start: monday,
    summary: 'Une semaine d’endurance, une séance au seuil et deux séances de force.',
    status: 'proposed',
    sessions: [
      ['2026-10-19', 'rest', 'Repos', 0, '', '', 'Récupérer du week-end'],
      ['2026-10-20', 'run', 'Seuil', 50, '5:00 /km', '3 x 10 min, 2 min de trot', 'Allure 10 km'],
      ['2026-10-21', 'class', 'Body Pump', 55, 'RPE 7', '', 'Force de tout le corps'],
      ['2026-10-23', 'run', 'Footing', 45, '6:00-6:20 /km', '', 'Endurance de base'],
      ['2026-10-25', 'ride', 'Sortie vélo', 90, 'Zone 2', '', 'Endurance sans impact'],
    ].map(([day, kind, title, duration_min, intensity, details, why]) => ({
      day,
      kind,
      title,
      duration_min,
      intensity,
      details,
      why,
    })),
  }
  await page.route('**/api/coach/status', (route) =>
    route.fulfill({
      json: {
        configured: true,
        model: 'gemini-3.8-flash',
        budget: {
          month: '2026-10',
          spent_eur: 0.5,
          limit_eur: 10,
          warning: false,
          exhausted: false,
        },
      },
    }),
  )
  const events = [
    ['tool', { name: 'get_goals_and_progress', label: 'lit tes objectifs' }],
    ['tool', { name: 'propose_weekly_plan', label: 'prépare un plan de semaine' }],
    ['plan', plan],
    ['text', { text: 'Voici une semaine **équilibrée** : allège si ta HRV baisse.' }],
    ['done', { cost_eur: 0.02, month_spent_eur: 0.52, month_limit_eur: 10 }],
  ]
  await page.route('**/api/coach/conversations/*/messages', (route) =>
    route.fulfill({
      contentType: 'text/event-stream',
      body: events.map(([n, d]) => `event: ${n}\ndata: ${JSON.stringify(d)}\n\n`).join(''),
    }),
  )
  await page.route('**/api/coach/plans/901', (route) =>
    route.fulfill({ json: { ...plan, status: 'accepted' } }),
  )
  await page.route('**/api/coach/plans/current', (route) =>
    route.fulfill({ json: { this_week: { ...plan, status: 'accepted' }, next_week: null } }),
  )

  await page.goto('/coach')
  await page.getByRole('button', { name: 'Nouvelle', exact: true }).click()
  await page.getByRole('button', { name: /plan pour la semaine prochaine/ }).click()
  const card = page.getByRole('article', { name: 'Plan de la semaine du 19 oct.' })
  await expect(card.getByText('3 x 10 min, 2 min de trot')).toBeVisible()
  await card.getByRole('button', { name: 'Accepter' }).click()
  await expect(card.getByText(/il est sur l’Accueil/)).toBeVisible()

  await page.getByRole('link', { name: 'Accueil' }).click()
  const home = page.getByRole('region', { name: 'Mon plan' })
  await expect(home.getByText('Body Pump')).toBeVisible()
  await expect(home.getByRole('button')).toHaveCount(0)
  if (process.env.E2E_SCREENSHOTS) {
    await home.screenshot({
      path: `${process.env.E2E_SCREENSHOTS}/plan-${testInfo.project.name}.png`,
    })
  }
})

test('Longévité page: its own coach', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Longévité' }).click()
  await expect(page.getByRole('heading', { name: 'Coach longévité' })).toBeVisible()
  await expect(page.getByRole('button', { name: /zone 2/ })).toBeVisible()
})
