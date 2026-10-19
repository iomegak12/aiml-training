import { problemToApiError, request, requestJson } from './apiClient'
import { readSse } from '../utils/sse'

/** POST /chat. `mode` is "chat" or "plan". */
export function sendChat({ message, threadId, mode = 'chat', signal }) {
  return requestJson('/chat', {
    method: 'POST',
    body: { message, thread_id: threadId || undefined, mode },
    signal,
  })
}

/** POST /chat/decision: approve or reject the pending plan of a plan thread. */
export function decidePlan({ threadId, approve, feedback, signal }) {
  return requestJson('/chat/decision', {
    method: 'POST',
    body: { thread_id: threadId, approve, feedback: feedback || undefined },
    signal,
  })
}

/**
 * POST /chat-streaming. Calls `onEvent({ event, data })` for every Server-Sent Event and
 * throws an ApiError when the stream reports an `error` event.
 */
export async function streamChat({ message, threadId, signal, onEvent }) {
  const response = await request('/chat-streaming', {
    method: 'POST',
    body: { message, thread_id: threadId || undefined },
    signal,
  })
  for await (const event of readSse(response.body)) {
    if (event.event === 'error') {
      throw problemToApiError(event.data)
    }
    onEvent(event)
  }
}
