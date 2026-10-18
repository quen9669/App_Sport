// The answers kept for offline use live in the service worker's "api-cache"
// (see vite.config.ts). Signing out empties it, so the data does not stay on a
// device after "Se déconnecter".
export const API_CACHE = 'api-cache'

export async function clearOfflineData() {
  try {
    localStorage.removeItem('app-sport:last-online')
  } catch {
    // Storage unavailable: nothing was kept there either.
  }
  if (!('caches' in window)) return
  await caches.delete(API_CACHE)
}
