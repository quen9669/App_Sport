// Tests for the app frame: the 3 folders, their tabs and the always-visible disclaimer.
import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'

afterEach(() => {
  vi.unstubAllGlobals()
})

// MemoryRouter = a router for tests, starting at the given URL.
function renderAt(url: string) {
  // A backend that never answers: only the frame is tested here.
  vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(() => {})))
  return render(
    <MemoryRouter initialEntries={[url]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App', () => {
  it('shows the 3 folders and the medical disclaimer', () => {
    renderAt('/')

    const folders = screen.getByRole('navigation', { name: 'Dossiers' })
    const links = within(folders).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual(['Entraînement', 'Santé', 'Coach'])
    expect(within(folders).getByRole('link', { name: 'Entraînement' })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(screen.getByRole('link', { name: 'Réglages' })).toHaveAttribute('href', '/profil')
    expect(screen.getByText(/pas un avis médical/)).toBeInTheDocument()
  })

  it('shows the tabs of the folder of the current page', () => {
    renderAt('/sante/sommeil')

    const tabs = screen.getByRole('navigation', { name: 'Onglets Santé' })
    expect(within(tabs).getByRole('link', { name: 'Sommeil' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    // The summary tab is not lit up by its sub-pages.
    expect(within(tabs).getByRole('link', { name: 'Résumé' })).not.toHaveAttribute('aria-current')
  })

  it('keeps an activity page in the Entraînement folder', () => {
    renderAt('/activites/42')

    const tabs = screen.getByRole('navigation', { name: 'Onglets Entraînement' })
    expect(within(tabs).getByRole('link', { name: 'Activités' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('lists every tab, settings included, in the PC sidebar', () => {
    renderAt('/')

    const menu = screen.getByRole('navigation', { name: 'Menu' })
    for (const name of ['Ma semaine', 'Mon plan', 'Tabac', 'Mes lieux', 'Sources']) {
      expect(within(menu).getByRole('link', { name })).toBeInTheDocument()
    }
  })
})
