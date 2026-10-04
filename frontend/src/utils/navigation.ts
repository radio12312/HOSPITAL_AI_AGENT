import {
  Bot,
  BedDouble,
  CalendarClock,
  LayoutDashboard,
  Siren,
  UserRound,
  UsersRound,
  type LucideIcon,
} from 'lucide-react'
import type { Role } from '../types'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

const dashboard: NavItem = { to: '/', label: 'Dashboard', icon: LayoutDashboard }
const patients: NavItem = { to: '/patients', label: 'Patients', icon: UserRound }
const appointments: NavItem = { to: '/appointments', label: 'Appointments', icon: CalendarClock }
const beds: NavItem = { to: '/beds', label: 'Beds', icon: BedDouble }
const staff: NavItem = { to: '/staff', label: 'Staff', icon: UsersRound }
const emergency: NavItem = { to: '/emergency', label: 'Emergency Center', icon: Siren }
const assistant: NavItem = { to: '/assistant', label: 'AI Assistant', icon: Bot }

export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  admin: [dashboard, patients, appointments, beds, staff, emergency, assistant],
  doctor: [dashboard, appointments, { ...patients, label: 'My Patients' }, beds, assistant],
  staff_coordinator: [dashboard, staff, assistant],
}

/** Route access by role; used both for guards and to hide nav items. */
export const ROUTE_ROLES: Record<string, Role[]> = {
  '/': ['admin', 'doctor', 'staff_coordinator'],
  '/patients': ['admin', 'doctor'],
  '/appointments': ['admin', 'doctor'],
  '/beds': ['admin', 'doctor'],
  '/staff': ['admin', 'staff_coordinator'],
  '/emergency': ['admin'],
  '/assistant': ['admin', 'doctor', 'staff_coordinator'],
}

export function pageTitle(pathname: string, role: Role | undefined): string {
  const items = role ? NAV_BY_ROLE[role] : []
  const match = items.find((i) => i.to === pathname)
  if (match) return match.label
  const fallback = NAV_BY_ROLE.admin.find((i) => i.to === pathname)
  return fallback?.label ?? 'Hospital Workflow Agent'
}
