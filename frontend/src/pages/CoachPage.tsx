// Coach pages: chat with the training coach ("/coach") or the longevity coach
// ("/longevite"), same screen, different texts. The answer arrives piece by
// piece (streaming); the tools the coach uses to read FRANKS's data are shown
// as they run ("lit ton sommeil…"), and a proposed weekly plan appears as a
// card to accept or modify. Conversations are kept by the backend; the
// month's cost and budget (both coaches together) are always visible.
import { useEffect, useRef, useState } from 'react'

import {
  askCoach,
  type CoachConversation,
  type CoachName,
  type CoachPlan,
  type CoachShownMessage,
  type CoachStatus,
  createConversation,
  decidePlan,
  deleteConversation,
  fetchCoachStatus,
  fetchConversation,
  fetchConversations,
} from '../api/client'
import CoachMemories from '../components/CoachMemories'
import CoachText from '../components/CoachText'
import PlanCard from '../components/PlanCard'
import { formatNumber } from '../utils/format'

interface CoachTexts {
  title: string
  subtitle: string
  suggestions: string[] // ready-made questions for an empty conversation
}

const COACHES: Record<CoachName, CoachTexts> = {
  training: {
    title: 'Coach muscu et cardio',
    subtitle: 'Programmation, progression, récupération et plan de la semaine',
    suggestions: [
      'Comment se passe ma préparation du 10 km du 13 décembre ?',
      'Mes séances de muscu progressent-elles ?',
      'Ma récupération de cette semaine permet-elle une séance intense demain ?',
      'Propose-moi un plan pour la semaine prochaine.',
    ],
  },
  longevity: {
    title: 'Coach longévité',
    subtitle: 'Zone 2, VO2max, force, sommeil, activité quotidienne et arrêt du tabac',
    suggestions: [
      'Fais-moi un bilan de ma santé sur les trois derniers mois.',
      'Est-ce que je fais assez d’endurance en zone 2 ?',
      'Comment évolue ma VO2max ?',
      'Où en est mon arrêt de la cigarette ?',
    ],
  },
}

const MODIFY_PREFIX = 'Modifie le plan : '

const euros = (value: number) => `${formatNumber(value, 2)} €`

export default function CoachPage({ coach }: { coach: CoachName }) {
  const texts = COACHES[coach]
  const [status, setStatus] = useState<CoachStatus | null>(null)
  const [conversations, setConversations] = useState<CoachConversation[]>([])
  const [current, setCurrent] = useState<number | null>(null)
  const [messages, setMessages] = useState<CoachShownMessage[]>([])
  const [answering, setAnswering] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [answers, setAnswers] = useState(0) // refreshes the memory panel after each answer
  const [question, setQuestion] = useState('')

  useEffect(() => {
    let cancelled = false
    Promise.all([fetchCoachStatus(), fetchConversations(coach)])
      .then(([coachStatus, list]) => {
        if (cancelled) return
        setStatus(coachStatus)
        setConversations(list)
        if (list[0]) void open(list[0].id)
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de joindre le coach.')
      })
    return () => {
      cancelled = true
    }
  }, [coach])

  async function open(id: number) {
    setError(null)
    const detail = await fetchConversation(id)
    setCurrent(id)
    setMessages(detail.messages)
  }

  function startNew() {
    setCurrent(null) // created on the first question, so no empty conversations pile up
    setMessages([])
    setError(null)
  }

  async function remove() {
    if (current === null) return
    await deleteConversation(current)
    const list = conversations.filter((c) => c.id !== current)
    setConversations(list)
    if (list[0]) await open(list[0].id)
    else startNew()
  }

  async function ask(question: string) {
    setError(null)
    setAnswering(true)
    let id = current
    try {
      if (id === null) {
        const created = await createConversation(coach)
        id = created.id
        setCurrent(id)
        setConversations((list) => [{ ...created, title: question.slice(0, 80) }, ...list])
      }
      // The question at once, then an empty coach message that fills up.
      setMessages((list) => [
        ...list,
        { role: 'user', text: question, tools: [], plans: [] },
        { role: 'assistant', text: '', tools: [], plans: [] },
      ])
      await askCoach(id, question, (event) => {
        if (event.type === 'text' || event.type === 'tool' || event.type === 'plan') {
          setMessages((list) => {
            const last = list.at(-1)!
            let updated: CoachShownMessage
            if (event.type === 'text') updated = { ...last, text: last.text + event.text }
            else if (event.type === 'tool')
              updated = { ...last, tools: [...last.tools, event.label] }
            else {
              const { type: _type, ...plan } = event
              updated = { ...last, plans: [...last.plans, plan] }
            }
            return [...list.slice(0, -1), updated]
          })
        } else if (event.type === 'done') {
          setStatus((old) =>
            old
              ? {
                  ...old,
                  budget: {
                    ...old.budget,
                    spent_eur: event.month_spent_eur,
                    warning: event.month_spent_eur >= 0.8 * event.month_limit_eur,
                  },
                }
              : old,
          )
        } else {
          setError(event.message)
        }
      })
    } catch {
      setError('Le coach ne répond pas. Vérifie que le backend tourne.')
    } finally {
      setAnswering(false)
      setAnswers((n) => n + 1)
      // Drop an empty coach bubble left by an error.
      setMessages((list) =>
        list.at(-1)?.role === 'assistant' && !list.at(-1)?.text && !list.at(-1)?.tools.length
          ? list.slice(0, -1)
          : list,
      )
    }
  }

  async function decide(plan: CoachPlan, accepted: boolean) {
    try {
      const updated = await decidePlan(plan.id, accepted)
      // Accepting a plan replaces any other accepted plan of the same week.
      setMessages((list) =>
        list.map((message) => ({
          ...message,
          plans: message.plans.map((p) => {
            if (p.id === updated.id) return updated
            const sameWeek = p.week_start === updated.week_start && p.status === 'accepted'
            return accepted && sameWeek ? { ...p, status: 'replaced' as const } : p
          }),
        })),
      )
    } catch {
      setError('Impossible d’enregistrer ton choix sur le plan.')
    }
  }

  return (
    <>
      <h1>{texts.title}</h1>
      <p className="subtitle">{texts.subtitle}</p>
      <p className="hint">Conseils d’entraînement et d’hygiène de vie, pas un avis médical.</p>
      {status && <StatusLine status={status} />}
      <section className="card coach" aria-label="Conversation avec le coach">
        <div className="coach-bar">
          <label>
            <span className="visually-hidden">Conversation</span>
            <select
              value={current ?? ''}
              onChange={(event) =>
                event.target.value ? void open(Number(event.target.value)) : startNew()
              }
            >
              <option value="">Nouvelle conversation</option>
              {conversations.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title || 'Sans titre'}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="secondary" onClick={startNew} disabled={answering}>
            Nouvelle
          </button>
          {current !== null && (
            <button type="button" className="secondary" onClick={remove} disabled={answering}>
              Supprimer
            </button>
          )}
        </div>
        <Messages
          messages={messages}
          answering={answering}
          onDecide={(plan, accepted) => void decide(plan, accepted)}
          onModify={() => setQuestion(MODIFY_PREFIX)}
        />
        {messages.length === 0 && !answering && (
          <div className="coach-suggestions">
            {texts.suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="secondary"
                disabled={!status?.configured}
                onClick={() => void ask(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <QuestionForm
          text={question}
          onChange={setQuestion}
          disabled={answering || !status?.configured}
          onAsk={ask}
        />
      </section>
      <CoachMemories coach={coach} refreshKey={answers} />
    </>
  )
}

function StatusLine({ status }: { status: CoachStatus }) {
  if (!status.configured) {
    return (
      <p className="notice" role="status">
        Le coach attend ta clé API Gemini : ajoute <code>GEMINI_API_KEY</code> dans le fichier{' '}
        <code>.env</code> (voir le guide), puis relance l’app.
      </p>
    )
  }
  const { spent_eur, limit_eur, warning, exhausted } = status.budget
  return (
    <p className={warning ? 'notice' : 'hint'} role="status">
      Ce mois-ci : {euros(spent_eur)} sur {euros(limit_eur)} de budget
      {exhausted
        ? ' : budget atteint, le coach est en pause jusqu’au mois prochain.'
        : warning
          ? ' : plus de 80 % du budget utilisé.'
          : '.'}
    </p>
  )
}

function Messages({
  messages,
  answering,
  onDecide,
  onModify,
}: {
  messages: CoachShownMessage[]
  answering: boolean
  onDecide: (plan: CoachPlan, accepted: boolean) => void
  onModify: () => void
}) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // Follow the answer as it grows (jsdom has no scrollIntoView).
    end.current?.scrollIntoView?.({ block: 'end' })
  }, [messages])
  return (
    <div className="coach-messages" aria-live="polite">
      {messages.map((message, i) => (
        <div key={i} className={`bubble bubble--${message.role}`}>
          {message.tools.length > 0 && (
            <ul className="coach-tools" aria-label="Données consultées">
              {message.tools.map((label, j) => (
                <li key={j}>{label}</li>
              ))}
            </ul>
          )}
          {message.role === 'assistant' ? (
            message.text ? (
              <CoachText text={message.text} />
            ) : (
              answering && <p className="hint">Le coach réfléchit…</p>
            )
          ) : (
            <p>{message.text}</p>
          )}
          {message.plans.map((plan) => (
            <PlanCard
              key={plan.id}
              plan={plan}
              disabled={answering}
              onDecide={(accepted) => onDecide(plan, accepted)}
              onModify={onModify}
            />
          ))}
        </div>
      ))}
      <div ref={end} />
    </div>
  )
}

function QuestionForm({
  text,
  onChange: setText,
  disabled,
  onAsk,
}: {
  text: string // kept by the page, so "Modifier" on a plan can start the message
  onChange: (text: string) => void
  disabled: boolean
  onAsk: (question: string) => Promise<void>
}) {
  const input = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    // "Modifier" fills the start of the message: put the cursor at the end.
    if (text === MODIFY_PREFIX) input.current?.focus()
  }, [text])
  function send() {
    const question = text.trim()
    if (!question || disabled) return
    setText('')
    void onAsk(question)
  }
  return (
    <form
      className="coach-form"
      aria-label="Poser une question"
      onSubmit={(event) => {
        event.preventDefault()
        send()
      }}
    >
      <label className="visually-hidden" htmlFor="coach-question">
        Ta question
      </label>
      <textarea
        ref={input}
        id="coach-question"
        rows={2}
        maxLength={4000}
        placeholder="Pose ta question au coach…"
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          // Enter sends, Shift+Enter goes to a new line (like most chats).
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            send()
          }
        }}
      />
      <button type="submit" className="button" disabled={disabled || !text.trim()}>
        Envoyer
      </button>
    </form>
  )
}
