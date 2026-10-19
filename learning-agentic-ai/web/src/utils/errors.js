// Plain-language messages for the API's error codes.

const MESSAGES = {
  RATE_LIMITED: {
    title: "You're moving fast!",
    message: 'You reached the limit of 100 messages per minute. Sending unlocks automatically when the timer ends.',
  },
  AGENT_NOT_READY: {
    title: 'The assistant is offline right now',
    message: "The AI service isn't configured or available. Check the bell icon for details, or try again later.",
  },
  UPSTREAM_AUTH_ERROR: {
    title: "The AI service didn't accept our credentials",
    message: 'Please contact the administrator to check the OpenAI API key.',
  },
  UPSTREAM_RATE_LIMITED: {
    title: 'The AI service is busy',
    message: 'The AI provider is rate limiting us right now. Please try again in a moment.',
  },
  UPSTREAM_ERROR: {
    title: "We couldn't get an answer from the AI service",
    message: 'The AI provider returned an error. Please try again.',
  },
  UPSTREAM_UNAVAILABLE: {
    title: "We couldn't reach the AI service",
    message: 'The AI provider is unreachable at the moment. Please try again shortly.',
  },
  THREAD_BUSY: {
    title: 'Still working on your previous message',
    message: 'This conversation is busy. Please wait a moment and try again.',
  },
  THREAD_MODE_MISMATCH: {
    title: 'This conversation is in a different mode',
    message: 'Start a new chat to switch between plan mode and regular chat for this conversation.',
  },
  THREAD_NOT_FOUND: {
    title: 'This conversation has expired',
    message: 'The server no longer knows this conversation (it may have restarted). Please start a new chat.',
  },
  PLAN_PENDING: {
    title: 'A plan is waiting for your decision',
    message: 'Approve or request changes to the current plan before asking for a new one.',
  },
  NO_PENDING_PLAN: {
    title: 'This plan was already decided',
    message: 'There is no plan waiting for approval in this conversation anymore.',
  },
  VALIDATION_ERROR: {
    title: "That message couldn't be sent",
    message: 'Please check your message and try again.',
  },
  NETWORK_ERROR: {
    title: "Can't reach the server",
    message: 'Check your connection and that the service is running, then try again.',
  },
  GATEWAY_ERROR: {
    title: 'The service is starting or unavailable',
    message: 'The API did not respond through the gateway. Please try again in a moment.',
  },
  INTERNAL_ERROR: {
    title: 'Something went wrong on our side',
    message: 'An unexpected error occurred. Please try again; share the request ID with support if it persists.',
  },
}

const NOT_RETRYABLE = new Set(['THREAD_MODE_MISMATCH', 'THREAD_NOT_FOUND', 'NO_PENDING_PLAN', 'PLAN_PENDING'])

/** Map an ApiError (or any error) to { title, message, canRetry }. */
export function describeError(error) {
  const known = MESSAGES[error?.code]
  if (known) {
    const message =
      error.code === 'VALIDATION_ERROR' && error.errors?.length
        ? `${known.message} (${error.errors.map((e) => e.msg).join('; ')})`
        : known.message
    return { ...known, message, canRetry: !NOT_RETRYABLE.has(error.code) }
  }
  return {
    title: 'Something went wrong',
    message: error?.detail || error?.message || 'The request failed. Please try again.',
    canRetry: true,
  }
}
