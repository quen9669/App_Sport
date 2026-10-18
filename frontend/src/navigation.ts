// The app's menu: three folders (FRANKS's choice), each with its own tabs,
// plus the settings reached from the gear icon. One place for every link, so
// the bottom bar (phone), the sidebar (PC) and the tabs never disagree.

export type FolderId = 'training' | 'health' | 'coach' | 'settings'

export interface Tab {
  to: string
  label: string
}

export interface Folder {
  id: FolderId
  label: string
  /** The tab the folder opens on (also the first of `tabs`). */
  home: Tab
  tabs: Tab[]
}

/** Builds a folder whose first tab is its home page. */
function folder(id: FolderId, label: string, home: Tab, others: Tab[]): Folder {
  return { id, label, home, tabs: [home, ...others] }
}

const TRAINING = folder('training', 'Entraînement', { to: '/', label: 'Ma semaine' }, [
  { to: '/activites', label: 'Activités' },
  { to: '/muscu', label: 'Muscu' },
  { to: '/course', label: 'Course' },
  { to: '/objectifs', label: 'Objectifs' },
])

export const FOLDERS: Folder[] = [
  TRAINING,
  folder('health', 'Santé', { to: '/sante', label: 'Résumé' }, [
    { to: '/sante/sommeil', label: 'Sommeil' },
    { to: '/sante/recuperation', label: 'Récupération' },
    { to: '/sante/activite', label: 'Activité' },
    { to: '/sante/poids', label: 'Poids' },
    { to: '/sante/tabac', label: 'Tabac' },
  ]),
  folder('coach', 'Coach', { to: '/coach', label: 'Muscu et cardio' }, [
    { to: '/longevite', label: 'Longévité' },
    { to: '/plan', label: 'Mon plan' },
  ]),
]

/** Not in the bottom bar: opened from the gear icon. */
export const SETTINGS = folder('settings', 'Réglages', { to: '/profil', label: 'Profil' }, [
  { to: '/sources', label: 'Sources' },
  { to: '/lieux', label: 'Mes lieux' },
])

const ALL = [...FOLDERS, SETTINGS]

/** True if `path` is this tab's page or one of its sub-pages (/activites/42). */
function matches(tab: Tab, path: string): boolean {
  if (tab.to === '/') return path === '/'
  // "/sante" must not also light up for "/sante/sommeil": only exact for folder roots.
  const isRootOfOthers = ALL.some((f) =>
    f.tabs.some((t) => t !== tab && t.to.startsWith(`${tab.to}/`)),
  )
  return path === tab.to || (!isRootOfOthers && path.startsWith(`${tab.to}/`))
}

/** The folder and tab of a URL; unknown pages fall back to the training folder. */
export function locate(path: string): { folder: Folder; tab: Tab | undefined } {
  for (const f of ALL) {
    const tab = f.tabs.find((t) => matches(t, path))
    if (tab) return { folder: f, tab }
  }
  return { folder: TRAINING, tab: undefined }
}

// The tabs of the Santé folder, as they appear in /sante/<section>.
export const HEALTH_SECTIONS = [
  'resume',
  'sommeil',
  'recuperation',
  'activite',
  'poids',
  'tabac',
] as const
export type HealthSection = (typeof HEALTH_SECTIONS)[number]

/** True for a known tab name, such as "sommeil" in /sante/sommeil. */
export function isHealthSection(value: string | undefined): value is HealthSection {
  return HEALTH_SECTIONS.some((section) => section === value)
}
