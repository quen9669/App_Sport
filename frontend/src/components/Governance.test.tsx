// Unit tests for <Governance />: freshness of each source, completeness, colour legend.
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { GarminStatus, StravaStatus, SyncLog } from '../api/client'
import Governance from './Governance'

const log = (source: string, hoursAgo: number, status: SyncLog['status'] = 'success'): SyncLog => ({
  id: 1,
  source,
  kind: 'scheduled',
  status,
  started_at: '',
  finished_at: new Date(Date.now() - hoursAgo * 3_600_000).toISOString(),
  items_created: 0,
  items_updated: 0,
  error: null,
})
const garmin = { configured: true, activity_history_complete: true } as GarminStatus
const strava = { configured: true, connected: true, history_complete: false } as StravaStatus

describe('Governance', () => {
  it('shows a fresh sync, a stale one and the incomplete history', () => {
    render(
      <Governance logs={[log('garmin', 1), log('strava', 10)]} garmin={garmin} strava={strava} />,
    )
    expect(screen.getByText(/Synchro il y a 1 h/)).toBeInTheDocument()
    expect(screen.getByText(/Synchro il y a 10 h/)).toBeInTheDocument()
    expect(screen.getByText(/Historique en cours d’import/)).toBeInTheDocument()
    expect(screen.getByText('Carte des couleurs')).toBeInTheDocument()
  })

  it('says never synchronised without any log', () => {
    render(<Governance logs={[]} garmin={garmin} strava={null} />)
    expect(screen.getByText(/jamais synchronisé/)).toBeInTheDocument()
  })
})
