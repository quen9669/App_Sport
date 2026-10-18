// Root component: navigation bar and the page matching the current URL.
import { NavLink, Route, Routes } from 'react-router-dom'

import HomePage from './pages/HomePage'
import SourcesPage from './pages/SourcesPage'

export default function App() {
  return (
    <>
      <nav className="nav" aria-label="Navigation principale">
        <NavLink to="/" end>
          Accueil
        </NavLink>
        <NavLink to="/sources">Sources</NavLink>
      </nav>
      <main className="app">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/sources" element={<SourcesPage />} />
        </Routes>
        <p className="disclaimer">
          Cette application donne des conseils d’entraînement, pas un avis médical.
        </p>
      </main>
    </>
  )
}
