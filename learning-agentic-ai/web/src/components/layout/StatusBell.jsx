import { useEffect, useRef, useState } from 'react'
import Icon from '../common/Icon'
import { useServiceStatus } from '../../hooks/useServiceStatus'
import { timeLabel } from '../../utils/format'
import styles from './StatusBell.module.css'

const CHECK_LABELS = {
  settings: 'Model settings',
  openai_api_key: 'OpenAI API key',
  database: 'Ticket database',
  agents: 'AI agents',
}

const STATUS_TEXT = {
  loading: 'Checking service status…',
  ready: 'All systems operational',
  not_ready: 'Assistant needs attention',
  unreachable: 'Service unreachable',
}

/** Bell with a status badge (polls /api/ready); click to see the readiness checks. */
export default function StatusBell() {
  const { status, checks, checkedAt, refresh } = useServiceStatus()
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    if (!open) return undefined
    const close = (event) => {
      if (event.type === 'keydown' ? event.key === 'Escape' : !rootRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const failing = Object.values(checks).filter((check) => !check.ok).length
  const badge = status === 'ready' ? null : status === 'unreachable' ? '!' : failing || null

  return (
    <div className={styles.root} ref={rootRef}>
      <button
        type="button"
        className={styles.bell}
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-label={`Service status: ${STATUS_TEXT[status]}`}
      >
        <Icon name="bell" size={19} />
        {badge !== null && <span className={styles.badge}>{badge}</span>}
        {status === 'ready' && <span className={styles.dot} aria-hidden="true" />}
      </button>

      {open && (
        <div className={styles.panel} role="dialog" aria-label="Service status">
          <div className={styles.header}>
            <span className={`${styles.statusDot} ${styles[status]}`} />
            <strong>{STATUS_TEXT[status]}</strong>
          </div>

          {Object.keys(checks).length > 0 ? (
            <ul className={styles.checks}>
              {Object.entries(checks).map(([name, check]) => (
                <li key={name} className={styles.check}>
                  <span className={check.ok ? styles.ok : styles.fail}>
                    <Icon name={check.ok ? 'check' : 'x'} size={14} strokeWidth={2.4} />
                  </span>
                  <span>
                    <span className={styles.checkName}>{CHECK_LABELS[name] || name}</span>
                    <span className={styles.checkDetail}>{check.detail}</span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className={styles.empty}>
              {status === 'unreachable' ? 'The API could not be reached through the gateway.' : 'Waiting for the first check…'}
            </p>
          )}

          <div className={styles.footer}>
            <span>{checkedAt ? `Checked at ${timeLabel(checkedAt)}` : ''}</span>
            <button type="button" className={styles.refresh} onClick={refresh}>
              <Icon name="refresh" size={14} /> Check now
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
