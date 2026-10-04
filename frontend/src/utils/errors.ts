import axios from 'axios'
import type { ApiErrorBody } from '../types'

/** Turns an axios / FastAPI error into a human-readable message. */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    if (error.code === 'ECONNABORTED') return 'The request timed out. Please try again.'
    if (!error.response) return 'Cannot reach the server. Check that the backend is running.'

    const { status, data } = error.response
    const detail = data?.detail
    if (typeof detail === 'string' && detail) return detail
    if (Array.isArray(detail) && detail.length > 0) {
      return detail
        .map((d) => {
          const field = d.loc?.filter((p) => p !== 'body').join('.')
          return field ? `${field}: ${d.msg}` : d.msg
        })
        .join('; ')
    }
    if (status === 403) return 'You do not have permission to perform this action.'
    if (status === 404) return 'The requested resource was not found.'
    if (status === 503) return 'The AI service is temporarily unavailable.'
    return `Request failed (HTTP ${status}).`
  }
  if (error instanceof Error) return error.message
  return 'Something went wrong.'
}
