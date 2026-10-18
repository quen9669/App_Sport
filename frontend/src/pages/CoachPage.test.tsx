// Unit tests for <CoachPage />: the streamed answer is a fake SSE body.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { CoachPlan, CoachStatus } from '../api/client'
import CoachText from '../components/CoachText'
import { fakeBackend } from '../test/fakeBackend'
import CoachPage from './CoachPage'

afterEach(() => {
  vi.unstubAllGlobals()
})

const status: CoachStatus = {
  configured: true,
  model: 'gemini-3.8-flash',
  budget: { month: '2026-10', spent_eur: 0.12, limit_eur: 10, warning: false, exhausted: false },
}

function sse(...events: [string, object][]): Response {
  const body = events.map(([name, data]) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`)
  return new Response(body.join(''), { headers: { 'Content-Type': 'text/event-stream' } })
}

const conversation = {
  id: 4,
  title: '',
  created_at: '2026-10-18T15:00:00Z',
  updated_at: '2026-10-18T15:00:00Z',
}

describe('CoachPage', () => {
  it('streams an answer with the data the coach read, and shows the cost', async () => {
    const fetchMock = fakeBackend({
      'GET /api/coach/status': status,
      'GET /api/coach/training/conversations': [],
      'GET /api/coach/training/memories': [],
      'POST /api/coach/training/conversations': { ...conversation, messages: [] },
      'POST /api/coach/conversations/4/messages': () =>
        sse(
          ['tool', { name: 'get_sleep', label: 'lit ton sommeil' }],
          ['text', { text: 'Tu dors **6,5 h**' }],
          ['text', { text: ' en moyenne.\n- Couche-toi plus tôt' }],
          ['done', { cost_eur: 0.02, month_spent_eur: 0.14, month_limit_eur: 10 }],
        ),
    })
    const user = userEvent.setup()
    render(<CoachPage coach="training" />)

    expect(await screen.findByText(/Ce mois-ci : 0,12 € sur 10 €/)).toBeInTheDocument()
    await user.type(screen.getByLabelText('Ta question'), 'Comment je dors ?{Enter}')

    const chat = screen.getByRole('region', { name: 'Conversation avec le coach' })
    expect(await within(chat).findByText('6,5 h')).toBeInTheDocument() // in bold
    expect(within(chat).getByText('Comment je dors ?', { selector: 'p' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Comment je dors ?' })).toBeInTheDocument()
    expect(within(chat).getByText('lit ton sommeil')).toBeInTheDocument()
    expect(within(chat).getByText('Couche-toi plus tôt')).toBeInTheDocument()
    expect(await screen.findByText(/Ce mois-ci : 0,14 €/)).toBeInTheDocument()
    const ask = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/messages'))
    expect(JSON.parse(String(ask?.[1]?.body))).toEqual({ text: 'Comment je dors ?' })
  })

  it('reopens the last conversation and shows an error from the coach', async () => {
    fakeBackend({
      'GET /api/coach/status': status,
      'GET /api/coach/training/conversations': [{ ...conversation, title: 'Mon 10 km' }],
      'GET /api/coach/conversations/4': {
        ...conversation,
        title: 'Mon 10 km',
        messages: [
          { role: 'user', text: 'Et mon 10 km ?', tools: [], plans: [] },
          {
            role: 'assistant',
            text: 'Prédiction 49:40.',
            tools: ['regarde tes prédictions'],
            plans: [],
          },
        ],
      },
      'GET /api/coach/training/memories': [],
      'POST /api/coach/conversations/4/messages': () =>
        sse(['error', { message: 'Budget du mois atteint.' }]),
    })
    const user = userEvent.setup()
    render(<CoachPage coach="training" />)

    expect(await screen.findByText('Prédiction 49:40.')).toBeInTheDocument()
    expect(screen.getByRole('combobox')).toHaveValue('4')
    await user.type(screen.getByLabelText('Ta question'), 'Et demain ?')
    await user.click(screen.getByRole('button', { name: 'Envoyer' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Budget du mois atteint.')
  })

  it('waits for the API key', async () => {
    fakeBackend({
      'GET /api/coach/status': { ...status, configured: false },
      'GET /api/coach/training/conversations': [],
      'GET /api/coach/training/memories': [],
    })
    render(<CoachPage coach="training" />)
    expect(await screen.findByText(/attend ta clé API Gemini/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Envoyer' })).toBeDisabled()
    expect(screen.getByRole('button', { name: /préparation du 10 km/ })).toBeDisabled()
  })

  it('lets FRANKS accept a memory proposed by the coach', async () => {
    let memories = [{ id: 1, text: 'Genou gauche fragile', status: 'proposed' }]
    const fetchMock = fakeBackend({
      'GET /api/coach/status': status,
      'GET /api/coach/training/conversations': [],
      'GET /api/coach/training/memories': () => memories,
      'PATCH /api/coach/memories/1': () => {
        memories = [{ ...memories[0]!, status: 'accepted' }]
        return memories[0]
      },
    })
    const user = userEvent.setup()
    render(<CoachPage coach="training" />)

    const panel = await screen.findByRole('region', { name: 'Ce que le coach retient' })
    await user.click(await within(panel).findByRole('button', { name: 'Accepter' }))
    expect(
      await within(panel).findByRole('button', { name: 'Oublier « Genou gauche fragile »' }),
    ).toBeInTheDocument()
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PATCH')).toBe(true),
    )
  })
})

const plan: CoachPlan = {
  id: 7,
  coach: 'training',
  week_start: '2026-10-19',
  summary: 'Semaine d’endurance avec une séance de seuil.',
  status: 'proposed',
  sessions: [
    {
      day: '2026-10-20',
      kind: 'run',
      title: 'Seuil',
      duration_min: 50,
      intensity: '5:00 /km',
      details: '3 x 10 min',
      why: 'Allure de course',
    },
    {
      day: '2026-10-21',
      kind: 'rest',
      title: 'Repos',
      duration_min: 0,
      intensity: '',
      details: '',
      why: 'Récupérer',
    },
  ],
}

describe('CoachPage plans', () => {
  it('shows a proposed plan as a card that FRANKS accepts', async () => {
    const fetchMock = fakeBackend({
      'GET /api/coach/status': status,
      'GET /api/coach/training/conversations': [],
      'GET /api/coach/training/memories': [],
      'POST /api/coach/training/conversations': { ...conversation, messages: [] },
      'POST /api/coach/conversations/4/messages': () =>
        sse(
          ['tool', { name: 'propose_weekly_plan', label: 'prépare un plan de semaine' }],
          ['plan', plan],
          ['text', { text: 'Voici ta semaine.' }],
          ['done', { cost_eur: 0.01, month_spent_eur: 0.13, month_limit_eur: 10 }],
        ),
      'PATCH /api/coach/plans/7': { ...plan, status: 'accepted' },
    })
    const user = userEvent.setup()
    render(<CoachPage coach="training" />)
    await screen.findByText(/Ce mois-ci/)
    await user.type(screen.getByLabelText('Ta question'), 'Un plan ?{Enter}')

    const card = await screen.findByRole('article', { name: 'Plan de la semaine du 19 oct.' })
    expect(within(card).getByText('Seuil')).toBeInTheDocument()
    expect(within(card).getByText(/5:00 \/km/)).toBeInTheDocument()
    expect(within(card).getByText('Allure de course')).toBeInTheDocument()
    await user.click(within(card).getByRole('button', { name: 'Accepter' }))
    expect(await within(card).findByText(/il est dans Mon plan/)).toBeInTheDocument()
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH')
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ accepted: true })
  })

  it('« Modifier » starts a message to the coach', async () => {
    fakeBackend({
      'GET /api/coach/status': status,
      'GET /api/coach/training/conversations': [conversation],
      'GET /api/coach/conversations/4': {
        ...conversation,
        messages: [
          { role: 'user', text: 'Un plan ?', tools: [], plans: [] },
          { role: 'assistant', text: 'Voici.', tools: [], plans: [plan] },
        ],
      },
      'GET /api/coach/training/memories': [],
    })
    const user = userEvent.setup()
    render(<CoachPage coach="training" />)
    await user.click(await screen.findByRole('button', { name: 'Modifier' }))
    expect(screen.getByLabelText('Ta question')).toHaveValue('Modifie le plan : ')
    expect(screen.getByLabelText('Ta question')).toHaveFocus()
  })

  it('the longevity coach has its own texts and conversations', async () => {
    fakeBackend({
      'GET /api/coach/status': status,
      'GET /api/coach/longevity/conversations': [],
      'GET /api/coach/longevity/memories': [],
    })
    render(<CoachPage coach="longevity" />)
    expect(await screen.findByRole('heading', { name: 'Coach longévité' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /zone 2/ })).toBeInTheDocument()
    expect(screen.getByText(/pas un avis médical/)).toBeInTheDocument()
  })
})

describe('CoachText', () => {
  it('renders simple Markdown without HTML injection', () => {
    render(<CoachText text={'## Plan\n1. Lundi\n2. Mardi\nTexte <img src=x> **gras**'} />)
    expect(screen.getByRole('heading', { name: 'Plan' })).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText(/Texte <img src=x>/)).toBeInTheDocument() // shown as text
    expect(document.querySelector('img')).toBeNull()
    expect(screen.getByText('gras').tagName).toBe('STRONG')
  })
})
