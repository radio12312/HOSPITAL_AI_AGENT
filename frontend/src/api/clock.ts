import { api } from './client'

export interface HospitalClock {
  now: string
  date: string
  active_scenario: string | null
}

/** The simulated hospital clock (set at seeding, moved by scenarios). */
export async function getClock(): Promise<HospitalClock> {
  const { data } = await api.get<HospitalClock>('/clock')
  return data
}
