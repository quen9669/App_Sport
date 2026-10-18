// Frontend entry point: mounts the React app into <div id="root"> of index.html.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import './styles/theme.css'

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
