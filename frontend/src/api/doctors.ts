import type { Doctor, ListResponse } from '../types'
import { api, cleanParams } from './client'

export async function listDoctors(department?: string): Promise<ListResponse<Doctor>> {
  const { data } = await api.get<ListResponse<Doctor>>('/doctors', {
    params: cleanParams({ department }),
  })
  return data
}
