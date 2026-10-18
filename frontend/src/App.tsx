// Root component: the app frame (menu in 3 folders, see navigation.ts) and the
// page matching the current URL.
import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useParams } from 'react-router-dom'

import AppShell from './components/AppShell'
import AuthGate from './components/AuthGate'
import CoachPage from './pages/CoachPage'
import GoalsPage from './pages/GoalsPage'
import { isHealthSection } from './navigation'
import HealthPage from './pages/HealthPage'
import HomePage from './pages/HomePage'
import PlacesPage from './pages/PlacesPage'
import PlanPage from './pages/PlanPage'
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

/** /sante/sommeil, /sante/poids...: an unknown section goes back to the summary. */
function HealthSection() {
  const { section } = useParams()
  if (!isHealthSection(section)) return <Navigate to="/sante" replace />
  return <HealthPage section={section} />
}

export default function App() {
  return (
    <AuthGate>
      <AppShell>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/activites" element={<Lazy page={<MapPage />} />} />
          {/* The old address of the map, kept so a bookmark still works. */}
          <Route path="/carte" element={<Navigate to="/activites" replace />} />
          <Route path="/activites/:id" element={<Lazy page={<ActivityPage />} />} />
          <Route path="/muscu" element={<StrengthPage />} />
          <Route path="/course" element={<RacePage />} />
          <Route path="/objectifs" element={<GoalsPage />} />
          <Route path="/sante" element={<HealthPage section="resume" />} />
          <Route path="/sante/:section" element={<HealthSection />} />
          {/* A key per coach: switching page starts from a fresh screen. */}
          <Route path="/coach" element={<CoachPage key="training" coach="training" />} />
          <Route path="/longevite" element={<CoachPage key="longevity" coach="longevity" />} />
          <Route path="/plan" element={<PlanPage />} />
          <Route path="/profil" element={<ProfilePage />} />
          <Route path="/sources" element={<SourcesPage />} />
          <Route path="/lieux" element={<PlacesPage />} />
        </Routes>
        <p className="disclaimer">
          Cette application donne des conseils d’entraînement, pas un avis médical.
        </p>
      </AppShell>
    </AuthGate>
  )
}
