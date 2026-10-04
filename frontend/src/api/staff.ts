import type {
  StaffListParams,
  StaffListResponse,
  StaffRebalanceRequest,
  StaffRebalanceResponse,
} from '../types'
import { api, cleanParams } from './client'

export async function listStaff(params: StaffListParams): Promise<StaffListResponse> {
  const { data } = await api.get<StaffListResponse>('/staff', { params: cleanParams(params) })
  return data
}

export async function rebalanceStaff(body: StaffRebalanceRequest): Promise<StaffRebalanceResponse> {
  const { data } = await api.post<StaffRebalanceResponse>('/staff/rebalance', body)
  return data
}
