import Button from '../common/Button'
import Icon from '../common/Icon'
import { describeError } from '../../utils/errors'
import styles from './ErrorBubble.module.css'

/** Friendly error with a rate-limit countdown, collapsible technical details and Retry. */
export default function ErrorBubble({ message, cooldownSeconds, busy, onRetry, onDismiss }) {
  const { error } = message
  const { title, message: text, canRetry } = describeError(error)
  const rateLimited = error?.code === 'RATE_LIMITED'
  const total = error?.retryAfter || 30
  const coolingDown = rateLimited && cooldownSeconds > 0

  return (
    <div className={styles.row} role="alert">
      <div className={styles.bubble}>
        <div className={styles.header}>
          <span className={styles.icon}>
            <Icon name={rateLimited ? 'clock' : 'alert'} size={18} />
          </span>
          <div className={styles.body}>
            <h3 className={styles.title}>{title}</h3>
            <p className={styles.text}>{text}</p>
          </div>
          <button type="button" className={styles.dismiss} onClick={onDismiss} aria-label="Dismiss">
            <Icon name="x" size={16} />
          </button>
        </div>

        {coolingDown && (
          <div className={styles.countdown}>
            <span>
              You can send again in <strong>{cooldownSeconds}s</strong>
            </span>
            <span className={styles.track}>
              <span className={styles.fill} style={{ width: `${(1 - cooldownSeconds / total) * 100}%` }} />
            </span>
          </div>
        )}

        <div className={styles.footer}>
          <details className={styles.details}>
            <summary>Details</summary>
            <dl>
              <dt>Code</dt>
              <dd>{error?.code || 'n/a'}</dd>
              {error?.status ? (
                <>
                  <dt>HTTP status</dt>
                  <dd>{error.status}</dd>
                </>
              ) : null}
              <dt>Request ID</dt>
              <dd>
                <code>{error?.requestId || 'n/a'}</code>
              </dd>
              {error?.detail && (
                <>
                  <dt>Server message</dt>
                  <dd>{error.detail}</dd>
                </>
              )}
            </dl>
          </details>
          {canRetry && message.retry && (
            <Button variant="outline" size="sm" icon="refresh" onClick={onRetry} disabled={busy || coolingDown}>
              Retry
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
