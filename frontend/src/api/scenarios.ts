import type { Scenario, ScenarioResetResponse, ScenarioRunResponse } from '../types'
import { api } from './client'

/** Note: this endpoint returns a bare array, not the usual { items, total } wrapper. */
export async function listScenarios(): Promise<Scenario[]> {
  const { data } = await api.get<Scenario[]>('/scenarios')
  return data
}

export async function runScenario(id: string): Promise<ScenarioRunResponse> {
  const { data } = await api.post<ScenarioRunResponse>(`/scenarios/${encodeURIComponent(id)}/run`)
  return data
}

export async function resetScenarios(): Promise<ScenarioResetResponse> {
  const { data } = await api.post<ScenarioResetResponse>('/scenarios/reset')
  return data
}
