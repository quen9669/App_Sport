// The frame around every page, in the Garmin Connect spirit (FRANKS's choice):
// - phone: a dark top bar with the folder's tabs, and the 3 folders at the bottom;
// - PC (wide screen, see theme.css): a dark sidebar with every folder and tab.
// Both are always in the page; CSS shows the right one for the screen width.
import type { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'

import logo from '../assets/logo.png'
import AppBanners from './AppBanners'
import { FOLDERS, locate, SETTINGS, type Folder } from '../navigation'
import { FolderIcon, GearIcon } from './icons'

export default function AppShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const { folder, tab } = locate(pathname)

  return (
    <div className="shell">
      <aside className="sidebar">
        <Link to="/" className="sidebar-brand">
          <img src={logo} alt="" width={44} height={38} />
          <span>App Sport</span>
        </Link>
        <nav aria-label="Menu" className="sidebar-nav">
          {FOLDERS.map((f) => (
            <FolderLinks key={f.id} folder={f} current={tab?.to} />
          ))}
          <FolderLinks folder={SETTINGS} current={tab?.to} />
        </nav>
      </aside>

      <div className="shell-main">
        <header className="topbar">
          <div className="topbar-row">
            <Link to="/" className="topbar-logo" aria-label="Accueil">
              <img src={logo} alt="" width={40} height={35} />
            </Link>
            <span className="topbar-folder">{folder.label}</span>
            <Link to="/profil" className="icon-button" aria-label="Réglages">
              <GearIcon />
            </Link>
          </div>
          <nav aria-label={`Onglets ${folder.label}`} className="tabs">
            {folder.tabs.map((t) => (
              <Link
                key={t.to}
                to={t.to}
                className={t.to === tab?.to ? 'active' : undefined}
                aria-current={t.to === tab?.to ? 'page' : undefined}
              >
                {t.label}
              </Link>
            ))}
          </nav>
        </header>

        <main className="app">
          <AppBanners />
          {children}
        </main>
      </div>

      <nav aria-label="Dossiers" className="bottom-bar">
        {FOLDERS.map((f) => (
          <Link
            key={f.id}
            to={f.home.to}
            className={f.id === folder.id ? 'active' : undefined}
            aria-current={f.id === folder.id ? 'true' : undefined}
          >
            <FolderIcon id={f.id} />
            {f.label}
          </Link>
        ))}
      </nav>
    </div>
  )
}

/** One folder in the sidebar: its name, then its tabs. */
function FolderLinks({ folder, current }: { folder: Folder; current: string | undefined }) {
  return (
    <div className="sidebar-folder">
      <span className="sidebar-folder-name">
        <FolderIcon id={folder.id} />
        {folder.label}
      </span>
      {folder.tabs.map((t) => (
        <Link
          key={t.to}
          to={t.to}
          className={t.to === current ? 'active' : undefined}
          aria-current={t.to === current ? 'page' : undefined}
        >
          {t.label}
        </Link>
      ))}
    </div>
  )
}
