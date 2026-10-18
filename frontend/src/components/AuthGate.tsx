// Shows the login screen when the app has a password and this device is not
// signed in yet (phase 6); otherwise shows the app. Any 401 from the backend
// (session expired, signed out elsewhere) brings the login screen back.
import { useEffect, useState, type ReactNode } from 'react'

import { AUTH_REQUIRED_EVENT, fetchAuthStatus } from '../api/client'
import LoginPage from '../pages/LoginPage'

type State = 'checking' | 'open' | 'login'

export default function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>('checking')

  useEffect(() => {
    let cancelled = false
    fetchAuthStatus()
      .then((status) => {
        if (!cancelled) setState(status.enabled && !status.authenticated ? 'login' : 'open')
      })
      .catch(() => {
        // Backend unreachable or offline: show the app, whose pages say what is
        // missing (offline, the last data kept on the device is still shown).
        if (!cancelled) setState('open')
      })
    const showLogin = () => setState('login')
    window.addEventListener(AUTH_REQUIRED_EVENT, showLogin)
    return () => {
      cancelled = true
      window.removeEventListener(AUTH_REQUIRED_EVENT, showLogin)
    }
  }, [])

  if (state === 'checking') return null // a split second: avoids a flash of either screen
  if (state === 'login') return <LoginPage onSuccess={() => setState('open')} />
  return <>{children}</>
}
