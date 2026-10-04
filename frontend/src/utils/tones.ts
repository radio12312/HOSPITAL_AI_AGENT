// Maps domain statuses to Badge tones (green ok, amber warning, red critical, sky info, slate maintenance).
import type {
  AppointmentStatus,
  AgentRunStatus,
  BedStatus,
  DoctorAvailability,
  EmergencySeverity,
  EmergencyStatus,
  InterruptReason,
  RecommendationStatus,
} from '../types'

export type Tone = 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'primary'

export function severityScoreTone(score: number): Tone {
  if (score >= 8) return 'danger'
  if (score >= 5) return 'warning'
  return 'success'
}

export function severityScoreLabel(score: number): string {
  if (score >= 8) return 'Critical'
  if (score >= 5) return 'Moderate'
  return 'Stable'
}

export const emergencySeverityTone: Record<EmergencySeverity, Tone> = {
  critical: 'danger',
  high: 'warning',
  moderate: 'info',
  low: 'success',
}

export const emergencyStatusTone: Record<EmergencyStatus, Tone> = {
  waiting: 'warning',
  in_treatment: 'info',
  resolved: 'success',
}

export const bedStatusTone: Record<BedStatus, Tone> = {
  available: 'success',
  occupied: 'danger',
  reserved: 'warning',
  maintenance: 'neutral',
}

/** Solid tile colours for the bed grid. */
export const bedTileClass: Record<BedStatus, string> = {
  available: 'bg-green-100 text-green-800 ring-green-300',
  occupied: 'bg-red-100 text-red-800 ring-red-300',
  reserved: 'bg-amber-100 text-amber-800 ring-amber-300',
  maintenance: 'bg-slate-200 text-slate-600 ring-slate-300',
}

export const appointmentStatusTone: Record<AppointmentStatus, Tone> = {
  scheduled: 'info',
  completed: 'success',
  cancelled: 'neutral',
  no_show: 'warning',
}

export const recommendationStatusTone: Record<RecommendationStatus, Tone> = {
  pending: 'warning',
  accepted: 'success',
  overridden: 'neutral',
}

export const doctorAvailabilityTone: Record<DoctorAvailability, Tone> = {
  available: 'success',
  busy: 'warning',
  off_duty: 'neutral',
}

export const runStatusTone: Record<AgentRunStatus, Tone> = {
  completed: 'success',
  needs_human: 'warning',
  rejected: 'neutral',
}

export function verdictTone(verdict: string): Tone {
  if (verdict === 'approve') return 'success'
  if (verdict === 'revise') return 'warning'
  return 'neutral'
}

export const interruptReasonLabel: Record<InterruptReason, string> = {
  infeasible: 'Infeasible',
  no_progress: 'No progress',
  cap: 'Rejected twice',
}

export function priorityTone(priority: string): Tone {
  const p = priority.toLowerCase()
  if (p.includes('critical')) return 'danger'
  if (p.includes('high')) return 'warning'
  if (p.includes('moderate') || p.includes('medium')) return 'info'
  return 'success'
}

/** Utilisation percentages: >= 90 critical, >= 75 warning. */
export function utilizationTone(pct: number): Tone {
  if (pct >= 90) return 'danger'
  if (pct >= 75) return 'warning'
  return 'success'
}

export const toneBarClass: Record<Tone, string> = {
  success: 'bg-green-500',
  warning: 'bg-amber-500',
  danger: 'bg-red-500',
  info: 'bg-sky-500',
  neutral: 'bg-slate-400',
  primary: 'bg-teal-700',
}
