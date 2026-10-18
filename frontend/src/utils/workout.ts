// How the steps of a run are written on screen, e.g. "6 × 800 m · 3:55-4:05 /km
// (fractionné) · récup 2 min". Paces come from the backend (`pace_targets`): the
// screen never computes them, so the watch and the page always agree.
import type { PaceKey, PaceRange, RunWorkout, WorkoutStep } from '../api/client'
import { formatPace } from './race'

export type PaceTargets = Partial<Record<PaceKey, PaceRange>>

export const PACE_LABELS: Record<PaceKey, string> = {
  none: 'libre',
  easy: 'endurance',
  marathon: 'allure marathon',
  threshold: 'seuil',
  interval: 'fractionné (VMA)',
  repetition: 'vitesse',
}

/** "15 min", "1 min 30", "800 m" or "5 km". */
export function stepLength(step: WorkoutStep): string {
  if (step.distance_m !== null) {
    const km = step.distance_m / 1000
    return step.distance_m >= 1000 && Number.isInteger(km * 10)
      ? `${km.toLocaleString('fr-FR')} km`
      : `${step.distance_m} m`
  }
  const seconds = step.duration_s ?? 0
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  if (minutes === 0) return `${rest} s`
  return rest === 0 ? `${minutes} min` : `${minutes} min ${String(rest).padStart(2, '0')}`
}

/** "5:00-5:30 /km (endurance)", or just "(endurance)" while the form is unknown. */
export function stepPace(step: WorkoutStep, targets: PaceTargets): string {
  if (step.pace === 'none') return ''
  const range = targets[step.pace]
  const label = `(${PACE_LABELS[step.pace]})`
  if (!range) return label
  // Fast pace first, as runners read a range: 3:55-4:05.
  return `${formatPace(range.fast_s_per_km)}-${formatPace(range.slow_s_per_km)} /km ${label}`
}

function join(...parts: string[]): string {
  return parts.filter(Boolean).join(' · ')
}

/** One line per step, in the order the watch will run them. */
export function workoutLines(workout: RunWorkout, targets: PaceTargets): string[] {
  const lines: string[] = []
  if (workout.warmup) {
    const step = workout.warmup
    lines.push(join('Échauffement', stepLength(step), stepPace(step, targets)))
  }
  for (const block of workout.blocks) {
    const work =
      block.repeats > 1 ? `${block.repeats} × ${stepLength(block.work)}` : stepLength(block.work)
    const recovery = block.recovery
      ? join(`récup ${stepLength(block.recovery)}`, stepPace(block.recovery, targets))
      : ''
    lines.push(join(work, stepPace(block.work, targets), recovery))
  }
  if (workout.cooldown) {
    const step = workout.cooldown
    lines.push(join('Retour au calme', stepLength(step), stepPace(step, targets)))
  }
  return lines
}
