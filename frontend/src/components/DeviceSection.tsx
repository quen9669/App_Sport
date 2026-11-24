// "Cet appareil" on the Profil page (phase 6): install the app, and sign out.
import { useEffect, useState } from 'react'

import { AUTH_REQUIRED_EVENT, fetchAuthStatus, logout } from '../api/client'
import { useLoad } from '../hooks/useLoad'
import { canInstall, isInstalled, onInstallChange, promptInstall } from '../pwa/install'
import { clearOfflineData } from '../pwa/offlineData'

export default function DeviceSection() {
  const [installable, setInstallable] = useState(canInstall)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => onInstallChange(() => setInstallable(canInstall())), [])

  // Offline: no status, so no sign-out button (it needs the backend anyway).
  const authEnabled = useLoad(fetchAuthStatus).data?.enabled ?? false

  async function install() {
    if (await promptInstall())
      setMessage('App installée : retrouve-la sur ton bureau ou ton écran d’accueil.')
  }

  async function signOut() {
    try {
      await logout()
    } catch {
      // Even if the backend is unreachable, forget everything on this device.
    }
    await clearOfflineData()
    window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT)) // back to the login screen
  }

  return (
    <section className="card" aria-labelledby="device-title">
      <h2 id="device-title">Cet appareil</h2>
      {isInstalled() ? (
        <p className="hint">L’app est installée sur cet appareil.</p>
      ) : installable ? (
        <button type="button" onClick={() => void install()}>
          Installer l’app
        </button>
      ) : (
        <p className="hint">
          Pour installer l’app : menu du navigateur, puis « Installer l’application » ou « Ajouter à
          l’écran d’accueil ».
        </p>
      )}
      {message && <p role="status">{message}</p>}
      {authEnabled && (
        <p>
          <button type="button" className="secondary" onClick={() => void signOut()}>
            Se déconnecter
          </button>{' '}
          <span className="hint">
            Les données gardées hors ligne sont effacées de cet appareil.
          </span>
        </p>
      )}
    </section>
  )
}
