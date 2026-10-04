import type { BedAllocateRequest, BedAllocateResponse, BedListParams, BedListResponse } from '../types'
import { api, cleanParams } from './client'

export async function listBeds(params: BedListParams): Promise<BedListResponse> {
  const { data } = await api.get<BedListResponse>('/beds', { params: cleanParams(params) })
  return data
}

export async function allocateBeds(body: BedAllocateRequest): Promise<BedAllocateResponse> {
  const { data } = await api.post<BedAllocateResponse>('/beds/allocate', body)
  return data
}
