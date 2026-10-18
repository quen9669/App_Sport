// The login screen (phase 6): the app's password, then 30 days without asking
// again on this device. After 5 wrong passwords the backend asks to wait 15 min.
import { useState, type FormEvent } from 'react'

import { ApiError, login } from '../api/client'
import logo from '../assets/logo.png'

export default function LoginPage({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault() // stay on the page: React handles the form
    setBusy(true)
    setError(null)
    try {
      await login(password)
      onSuccess()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Le serveur ne répond pas.')
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login">
      <form className="card login-card" onSubmit={(event) => void submit(event)}>
        <img src={logo} alt="" width={96} height={84} className="login-logo" />
        <h1>App Sport</h1>
        <label>
          Mot de passe
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            autoFocus
          />
        </label>
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy || password === ''}>
          {busy ? 'Connexion…' : 'Se connecter'}
        </button>
        <p className="hint">Tu restes connecté 30 jours sur cet appareil.</p>
      </form>
    </main>
  )
}
