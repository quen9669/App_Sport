// Root component: navigation bar and the page matching the current URL.
import { NavLink, Route, Routes } from 'react-router-dom'

import GoalsPage from './pages/GoalsPage'
import HomePage from './pages/HomePage'
import ProfilePage from './pages/ProfilePage'
import SourcesPage from './pages/SourcesPage'
import StrengthPage from './pages/StrengthPage'

export default function App() {
  return (
    <>
      <nav className="nav" aria-label="Navigation principale">
        <NavLink to="/" end>
          Accueil
        </NavLink>
        <NavLink to="/muscu">Muscu</NavLink>
        <NavLink to="/objectifs">Objectifs</NavLink>
        <NavLink to="/profil">Profil</NavLink>
        <NavLink to="/sources">Sources</NavLink>
      </nav>
      <main className="app">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/muscu" element={<StrengthPage />} />
          <Route path="/objectifs" element={<GoalsPage />} />
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
