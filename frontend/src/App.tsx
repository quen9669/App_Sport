// Root component. For phase 0 it only shows whether the backend answers.
import { useEffect, useState } from 'react'

import { fetchHealth } from './api/client'

/** The three states of the backend check, shown with different messages. */
type BackendStatus = 'loading' | 'ok' | 'error'

const STATUS_LABELS: Record<BackendStatus, string> = {
  loading: 'Connexion au backend…',
  ok: 'Backend OK',
  error: 'Backend injoignable',
}

export default function App() {
  const [status, setStatus] = useState<BackendStatus>('loading')

  // useEffect runs after the first render: the right place to call the API.
  useEffect(() => {
    // If the component disappears before the answer arrives, ignore the answer
    // (otherwise React would try to update a component that no longer exists).
    let cancelled = false
    fetchHealth()
      .then(() => {
        if (!cancelled) setStatus('ok')
      })
      .catch(() => {
        if (!cancelled) setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main className="app">
      <h1>App Sport</h1>
      <p className="subtitle">Ton application de sport personnelle</p>
      <p className={`status status--${status}`} role="status">
        {STATUS_LABELS[status]}
      </p>
      <p className="disclaimer">
        Cette application donne des conseils d’entraînement, pas un avis médical.
      </p>
    </main>
  )
}
