// The offline banner says since when the data shown dates.
import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { OfflineBanner } from './AppBanners'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('OfflineBanner', () => {
  it('appears offline with the time of the last data, and goes away online', () => {
    localStorage.setItem('app-sport:last-online', '2026-10-18T14:40:00Z')
    const onLine = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)

    render(<OfflineBanner />)
    expect(screen.getByRole('status')).toHaveTextContent(/Hors ligne : données du .*16:40/)

    onLine.mockReturnValue(true)
    act(() => {
      window.dispatchEvent(new Event('online'))
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
