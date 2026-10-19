import { useCallback } from 'react'
import { useChatSessions } from '../context/ChatSessionsContext'
import { decidePlan, sendChat, streamChat } from '../services/chatService'
import { truncate, uid } from '../utils/format'
import { useCountdown } from './useCountdown'

const DEFAULT_RETRY_AFTER_SECONDS = 30

function looksLikeToolError(content) {
  return typeof content === 'string' && /["']error["']\s*:/.test(content)
}

/**
 * Chat orchestration for the Support page: standard, streaming and plan-first requests,
 * plan decisions, errors with retry, and the rate-limit cooldown.
 */
export function useChat() {
  const { state, dispatch, getSession } = useChatSessions()
  const { sessions, activeId, busy, cooldownUntil, settings } = state

  const activeSession = sessions.find((s) => s.id === activeId) || null
  const pendingPlan = activeSession?.messages.find((m) => m.type === 'plan' && m.state === 'pending') || null
  const cooldownSeconds = useCountdown(cooldownUntil)

  // --- message helpers ------------------------------------------------------------

  const addMessage = useCallback(
    (sessionId, message) => {
      const full = { id: uid('msg'), createdAt: Date.now(), ...message }
      dispatch({ type: 'ADD_MESSAGE', sessionId, message: full })
      return full.id
    },
    [dispatch],
  )

  const updateMessage = useCallback(
    (sessionId, messageId, patch) => dispatch({ type: 'UPDATE_MESSAGE', sessionId, messageId, patch }),
    [dispatch],
  )

  const setBusy = useCallback((busyState) => dispatch({ type: 'SET_BUSY', busy: busyState }), [dispatch])

  const reportError = useCallback(
    (sessionId, error, retry) => {
      if (error?.name === 'AbortError') return
      if (error?.code === 'RATE_LIMITED') {
        const seconds = error.retryAfter || DEFAULT_RETRY_AFTER_SECONDS
        dispatch({ type: 'SET_COOLDOWN', until: Date.now() + seconds * 1000 })
      }
      addMessage(sessionId, { type: 'error', error, retry })
    },
    [addMessage, dispatch],
  )

  const addAssistantReply = useCallback(
    (sessionId, content) =>
      addMessage(sessionId, { type: 'assistant', content: content || '', activity: [], reasoning: '', streaming: false }),
    [addMessage],
  )

  // --- plan outcomes ----------------------------------------------------------------

  const handlePlanOutcome = useCallback(
    (sessionId, response, previousPlan = null) => {
      dispatch({ type: 'SET_THREAD', sessionId, mode: 'plan', threadId: response.thread_id })
      if (response.status === 'awaiting_approval') {
        addMessage(sessionId, {
          type: 'plan',
          threadId: response.thread_id,
          steps: response.plan || [],
          state: 'pending',
          revision: previousPlan ? previousPlan.revision + 1 : 1,
        })
      } else {
        addAssistantReply(sessionId, response.reply)
      }
    },
    [addAssistantReply, addMessage, dispatch],
  )

  // --- request runners ----------------------------------------------------------------

  const runStandard = useCallback(
    async (sessionId, text) => {
      setBusy({ phase: 'standard', sessionId, startedAt: Date.now() })
      try {
        const response = await sendChat({ message: text, threadId: getSession(sessionId)?.chatThreadId, mode: 'chat' })
        dispatch({ type: 'SET_THREAD', sessionId, mode: 'chat', threadId: response.thread_id })
        addAssistantReply(sessionId, response.reply)
      } catch (error) {
        reportError(sessionId, error, () => runStandard(sessionId, text))
      } finally {
        setBusy(null)
      }
    },
    [addAssistantReply, dispatch, getSession, reportError, setBusy],
  )

  const runStreaming = useCallback(
    async (sessionId, text) => {
      setBusy({ phase: 'streaming', sessionId, startedAt: Date.now(), receiving: false })
      let messageId = null
      const messageIdForEvents = () => {
        if (!messageId) {
          messageId = addMessage(sessionId, { type: 'assistant', content: '', activity: [], reasoning: '', streaming: true })
          dispatch({ type: 'PATCH_BUSY', patch: { receiving: true } })
        }
        return messageId
      }

      try {
        await streamChat({
          message: text,
          threadId: getSession(sessionId)?.chatThreadId,
          onEvent: ({ event, data }) => {
            switch (event) {
              case 'start':
                dispatch({ type: 'SET_THREAD', sessionId, mode: 'chat', threadId: data.thread_id })
                break
              case 'reasoning':
                updateMessage(sessionId, messageIdForEvents(), (m) => ({ reasoning: m.reasoning + data.text }))
                break
              case 'token':
                if (!data.subagent) {
                  updateMessage(sessionId, messageIdForEvents(), (m) => ({ content: m.content + data.text }))
                }
                break
              case 'tool_call':
                updateMessage(sessionId, messageIdForEvents(), (m) => ({
                  activity: [
                    ...m.activity,
                    { id: data.id || uid('tool'), name: data.name, args: data.args, subagent: data.subagent, status: 'running' },
                  ],
                }))
                break
              case 'tool_result':
                updateMessage(sessionId, messageIdForEvents(), (m) => ({
                  activity: m.activity.map((a) =>
                    a.id === data.tool_call_id ? { ...a, status: looksLikeToolError(data.content) ? 'error' : 'done' } : a,
                  ),
                }))
                break
              case 'done':
                updateMessage(sessionId, messageIdForEvents(), (m) => ({ content: m.content || data.reply || '', streaming: false }))
                break
              default:
                break
            }
          },
        })
      } catch (error) {
        reportError(sessionId, error, () => runStreaming(sessionId, text))
      } finally {
        if (messageId) {
          updateMessage(sessionId, messageId, (m) => ({
            streaming: false,
            activity: m.activity.map((a) => (a.status === 'running' ? { ...a, status: 'stopped' } : a)),
          }))
        }
        setBusy(null)
      }
    },
    [addMessage, dispatch, getSession, reportError, setBusy, updateMessage],
  )

  const runPlan = useCallback(
    async (sessionId, text) => {
      setBusy({ phase: 'plan', sessionId, startedAt: Date.now() })
      try {
        const response = await sendChat({ message: text, threadId: getSession(sessionId)?.planThreadId, mode: 'plan' })
        handlePlanOutcome(sessionId, response)
      } catch (error) {
        reportError(sessionId, error, () => runPlan(sessionId, text))
      } finally {
        setBusy(null)
      }
    },
    [getSession, handlePlanOutcome, reportError, setBusy],
  )

  // --- public actions -------------------------------------------------------------------

  const canSend = !busy && !pendingPlan && cooldownSeconds === 0

  const send = useCallback(
    (text) => {
      const message = text.trim()
      if (!message || !canSend) return false

      let sessionId = activeId
      if (!sessionId) {
        sessionId = uid('chat')
        dispatch({
          type: 'CREATE_SESSION',
          session: { id: sessionId, title: truncate(message), createdAt: Date.now(), chatThreadId: null, planThreadId: null, messages: [] },
        })
      }

      const mode = settings.planFirst ? 'plan' : settings.streaming ? 'streaming' : 'standard'
      addMessage(sessionId, { type: 'user', content: message, mode })

      if (mode === 'plan') runPlan(sessionId, message)
      else if (mode === 'streaming') runStreaming(sessionId, message)
      else runStandard(sessionId, message)
      return true
    },
    [activeId, addMessage, canSend, dispatch, runPlan, runStandard, runStreaming, settings],
  )

  const decide = useCallback(
    async (sessionId, plan, approve, feedback = '') => {
      updateMessage(sessionId, plan.id, {
        state: approve ? 'approved' : 'changes_requested',
        feedback: approve ? null : feedback,
        decidedAt: Date.now(),
      })
      setBusy({ phase: approve ? 'executing' : 'revising', sessionId, startedAt: Date.now() })
      try {
        const response = await decidePlan({ threadId: plan.threadId, approve, feedback })
        handlePlanOutcome(sessionId, response, plan)
      } catch (error) {
        const planGone = error?.code === 'NO_PENDING_PLAN' || error?.code === 'THREAD_NOT_FOUND'
        // The decision didn't reach the agent: let the user decide again.
        updateMessage(sessionId, plan.id, planGone ? { state: 'expired' } : { state: 'pending', feedback: null, decidedAt: null })
        reportError(sessionId, error, planGone ? null : () => decide(sessionId, plan, approve, feedback))
      } finally {
        setBusy(null)
      }
    },
    [handlePlanOutcome, reportError, setBusy, updateMessage],
  )

  const retry = useCallback(
    (sessionId, errorMessage) => {
      if (!errorMessage.retry || busy || cooldownSeconds > 0) return
      dispatch({ type: 'REMOVE_MESSAGE', sessionId, messageId: errorMessage.id })
      errorMessage.retry()
    },
    [busy, cooldownSeconds, dispatch],
  )

  const dismissError = useCallback(
    (sessionId, messageId) => dispatch({ type: 'REMOVE_MESSAGE', sessionId, messageId }),
    [dispatch],
  )

  const newChat = useCallback(() => dispatch({ type: 'NEW_CHAT' }), [dispatch])
  const selectSession = useCallback((sessionId) => dispatch({ type: 'SELECT_SESSION', sessionId }), [dispatch])
  const updateSettings = useCallback((patch) => dispatch({ type: 'SET_SETTINGS', patch }), [dispatch])

  return {
    sessions,
    activeSession,
    busy,
    settings,
    pendingPlan,
    cooldownSeconds,
    canSend,
    send,
    decide,
    retry,
    dismissError,
    newChat,
    selectSession,
    updateSettings,
  }
}
