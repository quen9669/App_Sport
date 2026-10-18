// "Installer l'app": Chrome (PC and Android) offers to install a PWA through the
// `beforeinstallprompt` event. It fires once, early, maybe before the Profil page
// is open: this module keeps it so the button can use it later.

/** The event Chrome sends (not yet in TypeScript's DOM types). */
export interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let deferred: InstallPromptEvent | null = null
const listeners = new Set<() => void>()

function notify() {
  listeners.forEach((listener) => listener())
}

/** Start listening (called once from main.tsx). */
export function captureInstallPrompt() {
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault() // no mini-banner from Chrome: our button asks instead
    deferred = event as InstallPromptEvent
    notify()
  })
  window.addEventListener('appinstalled', () => {
    deferred = null
    notify()
  })
}

export const canInstall = () => deferred !== null

/** Show Chrome's install dialog; true if FRANKS accepted. */
export async function promptInstall(): Promise<boolean> {
  if (!deferred) return false
  const event = deferred
  deferred = null // an install prompt can only be used once
  notify()
  await event.prompt()
  return (await event.userChoice).outcome === 'accepted'
}

/** Be told when installing becomes possible (or not anymore). Returns the "unsubscribe". */
export function onInstallChange(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Already opened as an installed app (no browser bar around it)? */
export const isInstalled = () => window.matchMedia?.('(display-mode: standalone)').matches ?? false
