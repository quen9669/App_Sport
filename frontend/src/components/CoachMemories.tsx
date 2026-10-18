// "Ce que le coach retient": the durable facts the coach gets with every
// question. The coach can only propose one; FRANKS accepts, corrects or
// removes it, and can add his own.
import { useEffect, useState } from 'react'

import {
  addMemory,
  type CoachMemory,
  type CoachName,
  deleteMemory,
  fetchMemories,
  updateMemory,
} from '../api/client'

interface Props {
  coach: CoachName
  refreshKey: number // changes after each answer: the coach may have proposed something
}

export default function CoachMemories({ coach, refreshKey }: Props) {
  const [memories, setMemories] = useState<CoachMemory[]>([])
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchMemories(coach)
      .then((list) => {
        if (!cancelled) setMemories(list)
      })
      .catch(() => {
        if (!cancelled) setError('Impossible de charger la mémoire du coach.')
      })
    return () => {
      cancelled = true
    }
  }, [coach, refreshKey])

  async function act(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
      setMemories(await fetchMemories(coach))
    } catch {
      setError('La modification n’a pas pu être enregistrée.')
    }
  }

  const proposed = memories.filter((m) => m.status === 'proposed')
  const accepted = memories.filter((m) => m.status === 'accepted')

  return (
    <section className="card" aria-labelledby="memory-title">
      <h2 id="memory-title">Ce que le coach retient</h2>
      <p className="hint">
        Ces informations sont données au coach à chaque question. Il peut en proposer, c’est toi qui
        valides.
      </p>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      {proposed.length > 0 && (
        <>
          <h3>Propositions du coach</h3>
          <ul className="goal-list">
            {proposed.map((memory) => (
              <li key={memory.id}>
                <span>{memory.text}</span>
                <span className="actions">
                  <button
                    type="button"
                    className="button"
                    onClick={() => act(() => updateMemory(memory.id, { accepted: true }))}
                  >
                    Accepter
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => act(() => deleteMemory(memory.id))}
                  >
                    Refuser
                  </button>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      {accepted.length === 0 ? (
        <p className="hint">Rien pour l’instant.</p>
      ) : (
        <ul className="goal-list">
          {accepted.map((memory) => (
            <li key={memory.id}>
              <span>{memory.text}</span>
              <button
                type="button"
                className="secondary"
                aria-label={`Oublier « ${memory.text} »`}
                onClick={() => act(() => deleteMemory(memory.id))}
              >
                Oublier
              </button>
            </li>
          ))}
        </ul>
      )}
      <form
        className="form form--inline"
        aria-label="Ajouter un souvenir"
        onSubmit={(event) => {
          event.preventDefault()
          const text = draft.trim()
          if (!text) return
          void act(() => addMemory(coach, text)).then(() => setDraft(''))
        }}
      >
        <label>
          À retenir
          <input
            value={draft}
            maxLength={300}
            placeholder="ex. Pas de course le lundi"
            onChange={(event) => setDraft(event.target.value)}
          />
        </label>
        <button type="submit" className="button">
          Ajouter
        </button>
      </form>
    </section>
  )
}
