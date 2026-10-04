import type { LoginRequest, LoginResponse, User } from '../types'
import { api } from './client'

export async function login(body: LoginRequest): Promise<LoginResponse> {
  const { data } = await api.post<LoginResponse>('/auth/login', body)
  return data
}

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>('/auth/me')
  return data
}
