import type {
  EmergencyCreateRequest,
  EmergencyCreateResponse,
  EmergencyListResponse,
  EmergencyListStatus,
  PaginationParams,
} from '../types'
import { api, cleanParams } from './client'

export async function listEmergencies(
  params: { status?: EmergencyListStatus } & PaginationParams,
): Promise<EmergencyListResponse> {
  const { data } = await api.get<EmergencyListResponse>('/emergency', { params: cleanParams(params) })
  return data
}

export async function createEmergency(body: EmergencyCreateRequest): Promise<EmergencyCreateResponse> {
  const { data } = await api.post<EmergencyCreateResponse>('/emergency', body)
  return data
}
