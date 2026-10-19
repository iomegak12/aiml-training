import { useRef, useState } from 'react'
import ChatHeader from './ChatHeader'
import ChatInput from './ChatInput'
import MessageList from './MessageList'
import SuggestionCards from './SuggestionCards'
import WelcomeHero from './WelcomeHero'
import styles from './ChatWindow.module.css'

function inputHint({ busy, pendingPlan, cooldownSeconds }) {
  if (cooldownSeconds > 0) return `Rate limit reached. You can send again in ${cooldownSeconds}s.`
  if (pendingPlan) return 'Approve the plan above or request changes to continue.'
  if (busy) return 'The assistant is working on your request…'
  return null
}

/** The main chat card: header with mode switches, messages (or welcome screen) and the input. */
export default function ChatWindow({ chat }) {
  const { activeSession, busy, settings, pendingPlan, cooldownSeconds, canSend } = chat
  const [draft, setDraft] = useState('')
  const inputRef = useRef(null)
  const isEmpty = !activeSession || activeSession.messages.length === 0

  const send = () => {
    if (chat.send(draft)) setDraft('')
  }

  const pickSuggestion = (suggestion) => {
    setDraft(suggestion.prompt)
    if (suggestion.enablePlan) chat.updateSettings({ planFirst: true })
    inputRef.current?.focus()
  }

  return (
    <section className={styles.window} aria-label="Chat">
      <ChatHeader settings={settings} onChange={chat.updateSettings} />

      {isEmpty ? (
        <div className={styles.welcome}>
          <WelcomeHero />
          <SuggestionCards onPick={pickSuggestion} />
        </div>
      ) : (
        <MessageList
          session={activeSession}
          busy={busy}
          cooldownSeconds={cooldownSeconds}
          onDecide={(plan, approve, feedback) => chat.decide(activeSession.id, plan, approve, feedback)}
          onRetry={(message) => chat.retry(activeSession.id, message)}
          onDismissError={(messageId) => chat.dismissError(activeSession.id, messageId)}
        />
      )}

      <ChatInput
        ref={inputRef}
        value={draft}
        onChange={setDraft}
        onSend={send}
        disabled={!canSend}
        hint={inputHint({ busy, pendingPlan, cooldownSeconds })}
      />
    </section>
  )
}
