import type {
  ListResponse,
  Recommendation,
  RecommendationDecisionRequest,
  RecommendationListParams,
} from '../types'
import { api, cleanParams } from './client'

export async function listRecommendations(
  params: RecommendationListParams,
): Promise<ListResponse<Recommendation>> {
  const { data } = await api.get<ListResponse<Recommendation>>('/recommendations', {
    params: cleanParams(params),
  })
  return data
}

export async function decideRecommendation(
  id: number,
  body: RecommendationDecisionRequest,
): Promise<Recommendation> {
  const { data } = await api.post<Recommendation>(`/recommendations/${id}/decision`, body)
  return data
}
