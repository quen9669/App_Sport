// Texts and small calculations of the Longévité tab. The backend sends numbers
// and codes ("met", "established"); every French word lives here, so the
// wording can change without touching the API.
import type { LongevityEvidence, LongevityIndicator, LongevityStatus } from '../api/client'
import { formatNumber } from './format'

export interface IndicatorText {
  label: string
  /** The public reference, or why there is none. */
  reference: string
  /** What the number covers ("moyenne des 4 dernières semaines"). */
  period: string
  /** Name of the earlier period, shown as "<previousLabel> : 1,8". */
  previousLabel: string
  digits: number
}

const WEEKS = 'moyenne des 4 dernières semaines complètes'
const DAYS = 'moyenne des 30 derniers jours'

export const INDICATOR_TEXTS: Record<string, IndicatorText> = {
  intensity_minutes: {
    label: 'Minutes d’intensité',
    reference: 'Repère OMS : 150 à 300 min par semaine (une minute intense compte double).',
    period: WEEKS,
    previousLabel: '4 semaines avant',
    digits: 0,
  },
  strength_sessions: {
    label: 'Séances de musculation',
    reference: 'Repère OMS : renforcement musculaire au moins 2 jours par semaine.',
    period: WEEKS,
    previousLabel: '4 semaines avant',
    digits: 1,
  },
  vo2max: {
    label: 'VO2max (estimation Garmin)',
    reference:
      'Pas de cible : la condition physique est l’un des meilleurs marqueurs de santé à long terme ; la tendance compte plus que la valeur.',
    period: 'dernière valeur',
    previousLabel: 'Il y a 3 mois',
    digits: 1,
  },
  steps: {
    label: 'Pas par jour',
    reference:
      'Les études voient le bénéfice grandir jusqu’à environ 8 000 pas par jour (adultes de moins de 60 ans), puis se stabiliser.',
    period: DAYS,
    previousLabel: '30 jours avant',
    digits: 0,
  },
  sleep_duration: {
    label: 'Durée de sommeil',
    reference: 'Repère : 7 à 9 heures par nuit pour un adulte.',
    period: DAYS,
    previousLabel: '30 jours avant',
    digits: 1,
  },
  sleep_regularity: {
    label: 'Régularité du coucher',
    reference: 'Écart type de l’heure de coucher : 30 min ou moins = régulier.',
    period: '30 dernières nuits',
    previousLabel: '30 nuits avant',
    digits: 0,
  },
  resting_hr: {
    label: 'FC au repos',
    reference:
      'Pas de cible : elle baisse souvent avec l’entraînement ; une hausse qui dure peut signaler fatigue ou maladie.',
    period: DAYS,
    previousLabel: '30 jours avant',
    digits: 0,
  },
  weight: {
    label: 'Poids',
    reference: 'Pas de cible ici : la tendance compte plus qu’une pesée.',
    period: 'dernière pesée',
    previousLabel: 'Il y a 3 mois',
    digits: 1,
  },
  bmi: {
    label: 'IMC',
    reference: 'Repère : 18,5 à 25. L’IMC ne distingue pas le muscle de la graisse.',
    period: 'avec ta taille du profil',
    previousLabel: 'Il y a 3 mois',
    digits: 1,
  },
}

/** Words, not only colours, for the verdict (colour-blind friendly). */
export const STATUS_LABELS: Record<LongevityStatus, string> = {
  met: 'Repère atteint',
  partly: 'En chemin',
  below: 'À travailler',
}

/** How solid the link with long-term health is (the spec asks to say it). */
export const EVIDENCE_LABELS: Record<LongevityEvidence, string> = {
  established: 'Preuve solide',
  likely: 'Preuve probable',
  uncertain: 'Preuve incertaine',
}

/** "2,2 séances/sem", "± 30 min", "–" without a value. */
export function formatIndicator(indicator: LongevityIndicator, value: number | null): string {
  if (value === null) return '–'
  const digits = INDICATOR_TEXTS[indicator.key]?.digits ?? 0
  const number = formatNumber(value, digits)
  if (indicator.key === 'sleep_regularity') return `± ${number} ${indicator.unit}`
  return `${number} ${indicator.unit}`
}

/** A signed difference, "+5", "−3,5" or "0" (a real minus sign, easier to read). */
export function formatChange(before: number | null, after: number | null, digits = 0): string {
  if (before === null || after === null) return '–'
  const factor = 10 ** digits
  const change = Math.round((after - before) * factor) / factor
  if (change === 0) return '0'
  const text = formatNumber(Math.abs(change), digits)
  return change > 0 ? `+${text}` : `−${text}`
}

// --- After quitting -----------------------------------------------------------

export interface Milestone {
  /** Days after the quit date from which it applies. */
  fromDay: number
  when: string
  text: string
}

/**
 * The WHO's timeline after stopping cigarettes ("Tobacco: health benefits of
 * smoking cessation"). It describes a COMPLETE stop: we show it as a guide,
 * with the reminder that the vape keeps the nicotine.
 */
export const QUIT_MILESTONES: Milestone[] = [
  {
    fromDay: 1,
    when: '12 heures',
    text: 'Le monoxyde de carbone dans le sang revient à un niveau normal.',
  },
  {
    fromDay: 14,
    when: '2 à 12 semaines',
    text: 'La circulation s’améliore et la fonction pulmonaire augmente.',
  },
  { fromDay: 30, when: '1 à 9 mois', text: 'La toux et l’essoufflement diminuent.' },
  {
    fromDay: 365,
    when: '1 an',
    text: 'Le risque de maladie coronarienne est environ la moitié de celui d’un fumeur.',
  },
  {
    fromDay: 5 * 365,
    when: '5 à 15 ans',
    text: 'Le risque d’AVC rejoint celui d’un non-fumeur.',
  },
  {
    fromDay: 10 * 365,
    when: '10 ans',
    text: 'Le risque de cancer du poumon est environ la moitié de celui d’un fumeur.',
  },
  {
    fromDay: 15 * 365,
    when: '15 ans',
    text: 'Le risque de maladie coronarienne rejoint celui d’un non-fumeur.',
  },
]

/** The milestones already reached, and the next one with the days left. */
export function milestoneProgress(daysSinceQuit: number): {
  reached: Milestone[]
  next: { milestone: Milestone; daysLeft: number } | null
} {
  const reached = QUIT_MILESTONES.filter((m) => daysSinceQuit >= m.fromDay)
  const upcoming = QUIT_MILESTONES.find((m) => daysSinceQuit < m.fromDay)
  return {
    reached,
    next: upcoming ? { milestone: upcoming, daysLeft: upcoming.fromDay - daysSinceQuit } : null,
  }
}

/** Names of the measures compared before / since quitting. */
export const COMPARISON_LABELS: Record<string, { label: string; digits: number }> = {
  resting_hr: { label: 'FC au repos', digits: 0 },
  hrv_ms: { label: 'HRV', digits: 0 },
  sleep_h: { label: 'Sommeil', digits: 1 },
  steps: { label: 'Pas par jour', digits: 0 },
}
