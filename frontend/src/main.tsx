// Frontend entry point: mounts the React app into <div id="root"> of index.html.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { polyfillCountryFlagEmojis } from 'country-flag-emoji-polyfill'
// "?url": Vite copies the font into the build and gives its local address.
import flagFont from 'country-flag-emoji-polyfill/dist/TwemojiCountryFlags.woff2?url'

// Fonts bundled with the app (no font CDN): Barlow for text, its semi-condensed cut for numbers.
import '@fontsource/barlow/400.css'
import '@fontsource/barlow/600.css'
import '@fontsource/barlow/700.css'
import '@fontsource/barlow-semi-condensed/600.css'
import '@fontsource/barlow-semi-condensed/700.css'

import App from './App'
import './styles/theme.css'

// Windows draws flag emojis as two letters ("LU"): on such browsers only, load a
// small font with the flags. It is served by the app itself, not by a CDN.
polyfillCountryFlagEmojis('Twemoji Country Flags', flagFont)

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
