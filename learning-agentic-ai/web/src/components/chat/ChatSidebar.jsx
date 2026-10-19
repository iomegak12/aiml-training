import { useMemo, useState } from 'react'
import Button from '../common/Button'
import Icon from '../common/Icon'
import { dayLabel } from '../../utils/format'
import styles from './ChatSidebar.module.css'

function matches(session, query) {
  if (!query) return true
  const needle = query.toLowerCase()
  return (
    session.title.toLowerCase().includes(needle) ||
    session.messages.some((m) => typeof m.content === 'string' && m.content.toLowerCase().includes(needle))
  )
}

function groupByDay(sessions) {
  const groups = new Map()
  for (const session of sessions) {
    const date = new Date(session.createdAt)
    const key = date.toDateString()
    if (!groups.has(key)) groups.set(key, { label: dayLabel(date), sessions: [] })
    groups.get(key).sessions.push(session)
  }
  return [...groups.values()]
}

function DayHeading({ label }) {
  if (label.text) return <h3 className={styles.day}>{label.text}</h3>
  return (
    <h3 className={styles.day}>
      {label.day}
      <sup>{label.suffix}</sup> {label.rest}
    </h3>
  )
}

/** Conversation history (in memory only) with search and a New Chat button. */
export default function ChatSidebar({ sessions, activeId, onSelect, onNewChat }) {
  const [query, setQuery] = useState('')
  const groups = useMemo(() => groupByDay(sessions.filter((s) => matches(s, query.trim()))), [sessions, query])

  return (
    <aside className={styles.sidebar} aria-label="Conversation history">
      <label className={styles.search}>
        <Icon name="search" size={19} />
        <input
          type="search"
          placeholder="Search history"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Search history"
        />
      </label>

      <div className={styles.list}>
        {sessions.length === 0 && (
          <p className={styles.empty}>
            Your conversations will appear here. They're kept only for this browser tab and cleared on refresh.
          </p>
        )}
        {sessions.length > 0 && groups.length === 0 && <p className={styles.empty}>No conversations match “{query}”.</p>}

        {groups.map((group) => (
          <section key={group.sessions[0].id} className={styles.group}>
            <DayHeading label={group.label} />
            {group.sessions.map((session) => (
              <button
                key={session.id}
                type="button"
                className={`${styles.item} ${session.id === activeId ? styles.active : ''}`}
                onClick={() => onSelect(session.id)}
                aria-current={session.id === activeId ? 'true' : undefined}
              >
                {session.title}
              </button>
            ))}
          </section>
        ))}
      </div>

      <Button variant="outline" icon="edit" className={styles.newChat} onClick={onNewChat}>
        New Chat
      </Button>
    </aside>
  )
}
