// Frontend entry point: mounts the React app into <div id="root"> of index.html.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import './styles/theme.css'

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Element #root not found in index.html')
}

// StrictMode runs extra checks in development to reveal bugs early.
createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
