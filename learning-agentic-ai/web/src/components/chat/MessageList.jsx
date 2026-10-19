import { useLayoutEffect, useRef } from 'react'
import AssistantMessage from './AssistantMessage'
import ErrorBubble from './ErrorBubble'
import PlanCard from './PlanCard'
import ThinkingIndicator from './ThinkingIndicator'
import UserMessage from './UserMessage'
import styles from './MessageList.module.css'

const NEAR_BOTTOM_PX = 140

/** Conversation messages; keeps scrolled to the bottom unless the user scrolled up to read. */
export default function MessageList({ session, busy, cooldownSeconds, onDecide, onRetry, onDismissError }) {
  const scrollRef = useRef(null)
  const stickToBottom = useRef(true)
  const lastCount = useRef(0)

  const thinking = busy && busy.sessionId === session.id && !busy.receiving
  const working = Boolean(busy)

  useLayoutEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const grew = session.messages.length > lastCount.current
    lastCount.current = session.messages.length
    if (stickToBottom.current || grew) {
      el.scrollTo({ top: el.scrollHeight, behavior: grew ? 'smooth' : 'auto' })
      stickToBottom.current = true
    }
  })

  const onScroll = () => {
    const el = scrollRef.current
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX
  }

  return (
    <div className={styles.scroll} ref={scrollRef} onScroll={onScroll}>
      <div className={styles.list} aria-live="polite">
        {session.messages.map((message) => {
          switch (message.type) {
            case 'user':
              return <UserMessage key={message.id} message={message} />
            case 'assistant':
              return <AssistantMessage key={message.id} message={message} />
            case 'plan':
              return (
                <PlanCard
                  key={message.id}
                  plan={message}
                  disabled={working || cooldownSeconds > 0}
                  executing={busy?.phase === 'executing' && busy.sessionId === session.id}
                  onApprove={() => onDecide(message, true)}
                  onRequestChanges={(feedback) => onDecide(message, false, feedback)}
                />
              )
            case 'error':
              return (
                <ErrorBubble
                  key={message.id}
                  message={message}
                  busy={working}
                  cooldownSeconds={cooldownSeconds}
                  onRetry={() => onRetry(message)}
                  onDismiss={() => onDismissError(message.id)}
                />
              )
            default:
              return null
          }
        })}
        {thinking && <ThinkingIndicator phase={busy.phase} startedAt={busy.startedAt} />}
      </div>
    </div>
  )
}
