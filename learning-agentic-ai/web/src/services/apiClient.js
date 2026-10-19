// Thin fetch wrapper for the API. Every call goes through nginx (or the Vite dev proxy) at /api.
// Failed responses are RFC 9457 Problem Details and are turned into ApiError.

export const API_BASE = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '')

export class ApiError extends Error {
  constructor({ status = 0, code = 'UNKNOWN_ERROR', title = 'Error', detail = '', requestId = null, retryAfter = null, errors = null }) {
    super(detail || title)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.title = title
    this.detail = detail
    this.requestId = requestId
    this.retryAfter = retryAfter
    this.errors = errors
  }
}

/** Build an ApiError from a Problem Details object (HTTP body or SSE `error` event). */
export function problemToApiError(problem = {}, fallback = {}) {
  return new ApiError({
    status: problem.status ?? fallback.status ?? 0,
    code: problem.code ?? fallback.code ?? 'UNKNOWN_ERROR',
    title: problem.title ?? fallback.title ?? 'Error',
    detail: problem.detail ?? fallback.detail ?? 'The request failed.',
    requestId: problem.request_id ?? fallback.requestId ?? null,
    retryAfter: problem.retry_after ?? fallback.retryAfter ?? null,
    errors: problem.errors ?? null,
  })
}

async function responseToApiError(response) {
  let problem = {}
  try {
    problem = await response.json()
  } catch {
    // not JSON (e.g. an nginx error page)
  }
  const retryAfterHeader = Number(response.headers.get('Retry-After'))
  return problemToApiError(problem, {
    status: response.status,
    code: response.status === 502 || response.status === 504 ? 'GATEWAY_ERROR' : `HTTP_${response.status}`,
    title: response.statusText || 'Error',
    detail: `The server responded with ${response.status}.`,
    requestId: response.headers.get('X-Request-ID'),
    retryAfter: Number.isFinite(retryAfterHeader) && retryAfterHeader > 0 ? retryAfterHeader : null,
  })
}

/** fetch() that throws ApiError for network failures and non-2xx responses. */
export async function request(path, { method = 'GET', body, signal, acceptAnyStatus = false } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError({ code: 'NETWORK_ERROR', title: 'Network error', detail: 'Could not reach the server.' })
  }
  if (!response.ok && !acceptAnyStatus) {
    throw await responseToApiError(response)
  }
  return response
}

export async function requestJson(path, options) {
  const response = await request(path, options)
  return response.json()
}
