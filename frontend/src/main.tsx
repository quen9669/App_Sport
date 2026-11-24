// Frontend entry point: mounts the React app into <div id="root"> of index.html.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { polyfillCountryFlagEmojis } from 'country-flag-emoji-polyfill'
// "?url": Vite copies the font into the build and gives its local address.
import flagFont from 'country-flag-emoji-polyfill/dist/TwemojiCountryFlags.woff2?url'

// Font bundled with the app (no font CDN): Figtree, a round geometric sans close to
// Strava's look. The colours live in theme.css; the library's own CSS only styles
// its small components (badges, pictograms).
import '@fontsource-variable/figtree'
import '@quen9669/lignes/tokens.css'
import '@quen9669/lignes/composants.css'

import App from './App'
import { captureInstallPrompt } from './pwa/install'
import './styles/theme.css'

// Windows draws flag emojis as two letters ("LU"): on such browsers only, load a
// small font with the flags. It is served by the app itself, not by a CDN.
polyfillCountryFlagEmojis('Twemoji Country Flags', flagFont)

// Keep Chrome's "install this app" offer for the button on the Profil page.
captureInstallPrompt()

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Element #root not found in index.html')
}

// StrictMode runs extra checks in development to reveal bugs early.
// BrowserRouter lets pages have their own URL (/sources) without reloading.
createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
