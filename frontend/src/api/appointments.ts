import type {
  Appointment,
  AppointmentCreateRequest,
  AppointmentCreateResponse,
  AppointmentListParams,
  ListResponse,
} from '../types'
import { api, cleanParams } from './client'

export async function listAppointments(
  params: AppointmentListParams,
): Promise<ListResponse<Appointment>> {
  const { data } = await api.get<ListResponse<Appointment>>('/appointments', {
    params: cleanParams(params),
  })
  return data
}

export async function createAppointment(
  body: AppointmentCreateRequest,
): Promise<AppointmentCreateResponse> {
  const { data } = await api.post<AppointmentCreateResponse>('/appointments', body)
  return data
}
