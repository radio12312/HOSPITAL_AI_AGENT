import type {
  AppointmentStatus,
  BedStatus,
  EmergencySeverity,
  PatientStatusFilter,
  Role,
  Shift,
} from '../types'

export const DEPARTMENTS = [
  'Cardiology',
  'General Medicine',
  'Orthopedics',
  'Neurology',
  'Pediatrics',
  'Oncology',
  'Emergency',
  'Surgery',
] as const

export const GENDERS = ['Female', 'Male', 'Other'] as const

export const PATIENT_STATUSES: { value: PatientStatusFilter; label: string }[] = [
  { value: 'admitted', label: 'Admitted' },
  { value: 'discharged', label: 'Discharged' },
  { value: 'all', label: 'All' },
]

export const APPOINTMENT_STATUSES: { value: AppointmentStatus; label: string }[] = [
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
  { value: 'no_show', label: 'No show' },
]

export const BED_STATUSES: { value: BedStatus; label: string }[] = [
  { value: 'available', label: 'Available' },
  { value: 'occupied', label: 'Occupied' },
  { value: 'reserved', label: 'Reserved' },
  { value: 'maintenance', label: 'Maintenance' },
]

export const SHIFTS: { value: Shift; label: string }[] = [
  { value: 'morning', label: 'Morning' },
  { value: 'evening', label: 'Evening' },
  { value: 'night', label: 'Night' },
]

export const EMERGENCY_SEVERITIES: { value: EmergencySeverity; label: string }[] = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'low', label: 'Low' },
]

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Admin',
  doctor: 'Doctor',
  staff_coordinator: 'Staff Coordinator',
}

export const SUGGESTED_QUESTIONS = [
  'Show bed utilization.',
  'Which ward is overloaded?',
  'Predict patient demand tomorrow.',
  'Why was a patient delayed?',
  'What staffing changes are recommended?',
  'Which resources are constrained?',
] as const

export const DASHBOARD_POLL_MS = 30_000
export const PAGE_SIZE = 20
