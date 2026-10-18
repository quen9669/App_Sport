// Unit tests for <HomePage />. `fetch` is replaced by a fake so no backend is needed.
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import HomePage from './HomePage'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('HomePage', () => {
  it('shows "Backend OK" when the health check succeeds', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ status: 'ok', version: '0.1.0' }), { status: 200 }),
        ),
    )

    render(<HomePage />)

    // findBy* waits until the text appears (the API call is asynchronous).
    expect(await screen.findByText('Backend OK')).toBeInTheDocument()
  })

  it('shows an error message when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Network error')))

    render(<HomePage />)

    expect(await screen.findByText('Backend injoignable')).toBeInTheDocument()
  })
})
