import type { AgentQueryRequest, AgentQueryResponse, AgentResumeRequest } from '../types'
import { api } from './client'

export async function queryAgent(body: AgentQueryRequest): Promise<AgentQueryResponse> {
  const { data } = await api.post<AgentQueryResponse>('/agent/query', body)
  return data
}

/** Admin only: resumes a run paused with status "needs_human". */
export async function resumeAgent(body: AgentResumeRequest): Promise<AgentQueryResponse> {
  const { data } = await api.post<AgentQueryResponse>('/agent/resume', body)
  return data
}
