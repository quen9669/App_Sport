// Two banners at the top of every page (phase 6):
// - offline: the data shown is the last kept on the device, and when it dates from;
// - a new version of the app is ready: reload when it suits FRANKS, not by surprise.
import { useEffect, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'

import { lastOnline } from '../api/client'
import { formatDayTime } from '../utils/format'

export default function AppBanners() {
  return (
    <>
      <OfflineBanner />
      <UpdateBanner />
    </>
  )
}

export function OfflineBanner() {
  const [online, setOnline] = useState(() => navigator.onLine)

  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update)
    window.addEventListener('offline', update)
    return () => {
      window.removeEventListener('online', update)
      window.removeEventListener('offline', update)
    }
  }, [])

  if (online) return null
  const since = lastOnline()
  return (
    <p className="banner banner--offline" role="status">
      Hors ligne
      {since ? ` : données du ${formatDayTime(since.toISOString())}` : ''}. Les modifications
      attendront le retour du réseau.
    </p>
  )
}

function UpdateBanner() {
  // needRefresh = a new version is downloaded and waiting.
  const {
    needRefresh: [needRefresh],
    updateServiceWorker,
  } = useRegisterSW()

  if (!needRefresh) return null
  return (
    <p className="banner banner--update" role="status">
      Une nouvelle version de l’app est prête.{' '}
      <button type="button" className="secondary" onClick={() => void updateServiceWorker(true)}>
        Recharger
      </button>
    </p>
  )
}
