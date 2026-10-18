// Tests for the app shell: navigation and the always-visible disclaimer.
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('shows the navigation and the medical disclaimer', () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))

    // MemoryRouter = a router for tests, starting at the given URL.
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Sources' })).toBeInTheDocument()
    expect(screen.getByText(/pas un avis médical/)).toBeInTheDocument()
  })
})
