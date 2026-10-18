// "Mes lieux": the places used for activities without GPS (gyms), and which
// one is the default for strength sessions and for the rest.
// Coordinates can be copied from any map app (long press in Google Maps or
// OpenStreetMap shows "49.6004, 6.1319").
import { useCallback, useEffect, useState, type FormEvent } from 'react'

import {
  ApiError,
  createPlace,
  deletePlace,
  fetchPlaces,
  updatePlace,
  type Place,
  type PlaceRole,
} from '../api/client'
import { parseCoordinates } from '../utils/activity'

const ROLE_LABELS: Record<PlaceRole, string> = {
  strength_default: 'Par défaut pour la muscu',
  other_default: 'Par défaut pour le reste',
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : 'Le backend ne répond pas.'
}

export default function PlacesPanel() {
  const [places, setPlaces] = useState<Place[]>([])
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    try {
      setPlaces(await fetchPlaces())
    } catch (err) {
      setError(errorText(err))
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchPlaces()
      .then((list) => {
        if (!cancelled) setPlaces(list)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(errorText(err))
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function run(action: () => Promise<unknown>) {
    setError(null)
    try {
      await action()
      await reload()
    } catch (err) {
      setError(errorText(err))
    }
  }

  return (
    <section className="card" aria-labelledby="places-title">
      <h2 id="places-title">Mes lieux</h2>
      <p className="hint">
        Les séances sans GPS sont placées ici sur la carte. Tu peux aussi choisir le lieu d’une
        séance depuis son détail.
      </p>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <ul className="place-list">
        {places.map((place) => (
          <PlaceRow
            key={`${place.id}-${place.role}`}
            place={place}
            onSave={(change) => run(() => updatePlace(place.id, change))}
            onDelete={() => run(() => deletePlace(place.id))}
          />
        ))}
      </ul>
      <NewPlaceForm
        onCreate={(name, lat, lng) =>
          run(() => createPlace({ name, latitude: lat, longitude: lng }))
        }
      />
    </section>
  )
}

function PlaceRow({
  place,
  onSave,
  onDelete,
}: {
  place: Place
  onSave: (change: {
    name: string
    latitude: number
    longitude: number
    role: PlaceRole | null
  }) => void
  onDelete: () => void
}) {
  const [name, setName] = useState(place.name)
  const [coords, setCoords] = useState(`${place.latitude}, ${place.longitude}`)
  const [role, setRole] = useState<PlaceRole | ''>(place.role ?? '')
  const parsed = parseCoordinates(coords)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!parsed || !name.trim()) return
    onSave({ name: name.trim(), latitude: parsed[0], longitude: parsed[1], role: role || null })
  }

  return (
    <li>
      <form className="place-form" onSubmit={submit} aria-label={`Lieu ${place.name}`}>
        <label>
          Nom
          <input value={name} maxLength={120} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          Coordonnées (latitude, longitude)
          <input value={coords} onChange={(event) => setCoords(event.target.value)} />
        </label>
        {!parsed && <p className="field-error">Format attendu : 49.6004, 6.1319</p>}
        <label>
          Rôle
          <select value={role} onChange={(event) => setRole(event.target.value as PlaceRole | '')}>
            <option value="">Aucun</option>
            <option value="strength_default">{ROLE_LABELS.strength_default}</option>
            <option value="other_default">{ROLE_LABELS.other_default}</option>
          </select>
        </label>
        <div className="actions">
          <button type="submit" disabled={!parsed || !name.trim()}>
            Enregistrer
          </button>
          <button type="button" className="secondary" onClick={onDelete}>
            Supprimer
          </button>
        </div>
      </form>
    </li>
  )
}

function NewPlaceForm({
  onCreate,
}: {
  onCreate: (name: string, lat: number, lng: number) => void
}) {
  const [name, setName] = useState('')
  const [coords, setCoords] = useState('')
  const parsed = parseCoordinates(coords)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!parsed || !name.trim()) return
    onCreate(name.trim(), parsed[0], parsed[1])
    setName('')
    setCoords('')
  }

  return (
    <form className="place-form" onSubmit={submit} aria-label="Nouveau lieu">
      <h3>Ajouter un lieu</h3>
      <label>
        Nom
        <input value={name} maxLength={120} onChange={(event) => setName(event.target.value)} />
      </label>
      <label>
        Coordonnées (latitude, longitude)
        <input
          value={coords}
          placeholder="49.6004, 6.1319"
          onChange={(event) => setCoords(event.target.value)}
        />
      </label>
      <div className="actions">
        <button type="submit" disabled={!parsed || !name.trim()}>
          Ajouter
        </button>
      </div>
    </form>
  )
}
