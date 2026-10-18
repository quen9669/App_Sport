// Root component: navigation bar and the page matching the current URL.
import { lazy, Suspense } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'

import GoalsPage from './pages/GoalsPage'
import HealthPage from './pages/HealthPage'
import HomePage from './pages/HomePage'
import ProfilePage from './pages/ProfilePage'
import RacePage from './pages/RacePage'
import SourcesPage from './pages/SourcesPage'
import StrengthPage from './pages/StrengthPage'

// The map pages need Leaflet: loaded only when one of them is opened.
const MapPage = lazy(() => import('./pages/MapPage'))
const ActivityPage = lazy(() => import('./pages/ActivityPage'))

function Lazy({ page }: { page: React.ReactNode }) {
  return <Suspense fallback={<p className="hint">Chargement…</p>}>{page}</Suspense>
}

export default function App() {
  return (
    <>
      <nav className="nav" aria-label="Navigation principale">
        <NavLink to="/" end>
          Accueil
        </NavLink>
        <NavLink to="/muscu">Muscu</NavLink>
        <NavLink to="/objectifs">Objectifs</NavLink>
        <NavLink to="/sante">Santé</NavLink>
        <NavLink to="/carte">Carte</NavLink>
        <NavLink to="/course">Course</NavLink>
        <NavLink to="/profil">Profil</NavLink>
        <NavLink to="/sources">Sources</NavLink>
      </nav>
      <main className="app">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/muscu" element={<StrengthPage />} />
          <Route path="/objectifs" element={<GoalsPage />} />
          <Route path="/sante" element={<HealthPage />} />
          <Route path="/carte" element={<Lazy page={<MapPage />} />} />
          <Route path="/course" element={<RacePage />} />
          <Route path="/activites/:id" element={<Lazy page={<ActivityPage />} />} />
          <Route path="/profil" element={<ProfilePage />} />
          <Route path="/sources" element={<SourcesPage />} />
        </Routes>
        <p className="disclaimer">
          Cette application donne des conseils d’entraînement, pas un avis médical.
        </p>
      </main>
    </>
  )
}
