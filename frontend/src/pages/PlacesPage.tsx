// "Mes lieux" (Réglages): where the sessions without GPS are placed on the map.
// The panel used to sit under the map; it is a setting, so it lives here now.
import PlacesPanel from '../components/PlacesPanel'

export default function PlacesPage() {
  return (
    <>
      <h1>Mes lieux</h1>
      <p className="subtitle">Les salles et lieux de tes séances sans GPS</p>
      <PlacesPanel />
    </>
  )
}
