import type { ListResponse, Patient, PatientCreateRequest, PatientListParams } from '../types'
import { api, cleanParams } from './client'

export async function listPatients(params: PatientListParams): Promise<ListResponse<Patient>> {
  const { data } = await api.get<ListResponse<Patient>>('/patients', { params: cleanParams(params) })
  return data
}

export async function createPatient(body: PatientCreateRequest): Promise<Patient> {
  const { data } = await api.post<Patient>('/patients', body)
  return data
}
