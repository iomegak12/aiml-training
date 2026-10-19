import { createContext, useCallback, useContext, useMemo, useReducer, useRef } from 'react'

// In-memory chat state (never persisted): sessions survive page navigation, not a refresh.
//
// session: { id, title, createdAt, chatThreadId, planThreadId, messages[] }
// message: { id, type: 'user' | 'assistant' | 'plan' | 'error', createdAt, ...type-specific fields }

const ChatSessionsContext = createContext(null)

const initialState = {
  sessions: [],
  activeId: null,
  busy: null, // { phase, sessionId, startedAt, receiving } while a request runs
  cooldownUntil: null, // epoch ms until which sending is rate limited
  settings: { streaming: true, planFirst: false },
}

function updateSession(state, sessionId, update) {
  return { ...state, sessions: state.sessions.map((s) => (s.id === sessionId ? update(s) : s)) }
}

function reducer(state, action) {
  switch (action.type) {
    case 'CREATE_SESSION':
      return { ...state, sessions: [action.session, ...state.sessions], activeId: action.session.id }
    case 'SELECT_SESSION':
      return { ...state, activeId: action.sessionId }
    case 'NEW_CHAT':
      return { ...state, activeId: null }
    case 'ADD_MESSAGE':
      return updateSession(state, action.sessionId, (s) => ({ ...s, messages: [...s.messages, action.message] }))
    case 'UPDATE_MESSAGE':
      return updateSession(state, action.sessionId, (s) => ({
        ...s,
        messages: s.messages.map((m) =>
          m.id === action.messageId ? { ...m, ...(typeof action.patch === 'function' ? action.patch(m) : action.patch) } : m,
        ),
      }))
    case 'REMOVE_MESSAGE':
      return updateSession(state, action.sessionId, (s) => ({
        ...s,
        messages: s.messages.filter((m) => m.id !== action.messageId),
      }))
    case 'SET_THREAD':
      return updateSession(state, action.sessionId, (s) => ({
        ...s,
        [action.mode === 'plan' ? 'planThreadId' : 'chatThreadId']: action.threadId,
      }))
    case 'SET_BUSY':
      return { ...state, busy: action.busy }
    case 'PATCH_BUSY':
      return state.busy ? { ...state, busy: { ...state.busy, ...action.patch } } : state
    case 'SET_COOLDOWN':
      return { ...state, cooldownUntil: action.until }
    case 'SET_SETTINGS':
      return { ...state, settings: { ...state.settings, ...action.patch } }
    default:
      throw new Error(`Unknown action: ${action.type}`)
  }
}

export function ChatSessionsProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const stateRef = useRef(state)
  stateRef.current = state

  const getSession = useCallback((sessionId) => stateRef.current.sessions.find((s) => s.id === sessionId), [])

  const value = useMemo(() => ({ state, dispatch, getSession }), [state, getSession])
  return <ChatSessionsContext.Provider value={value}>{children}</ChatSessionsContext.Provider>
}

export function useChatSessions() {
  const context = useContext(ChatSessionsContext)
  if (!context) throw new Error('useChatSessions must be used inside <ChatSessionsProvider>')
  return context
}
