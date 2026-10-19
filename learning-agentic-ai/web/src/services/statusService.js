import { request } from './apiClient'

/**
 * GET /ready. Returns `{ status: "ready" | "not_ready", checks }` for 200 and 503 alike,
 * or `{ status: "unreachable" }` when the API can't be reached.
 */
export async function getReadiness({ signal } = {}) {
  try {
    const response = await request('/ready', { signal, acceptAnyStatus: true })
    if (response.status !== 200 && response.status !== 503) {
      return { status: 'unreachable', checks: {} }
    }
    return await response.json()
  } catch (error) {
    if (error.name === 'AbortError') throw error
    return { status: 'unreachable', checks: {} }
  }
}
