import type { DashboardResponse } from '../types'
import { api } from './client'

export async function getDashboard(): Promise<DashboardResponse> {
  const { data } = await api.get<DashboardResponse>('/dashboard')
  return data
}
