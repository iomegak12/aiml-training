import { useState } from 'react'
import Button from '../common/Button'
import Icon from '../common/Icon'
import { timeLabel } from '../../utils/format'
import { AssistantAvatar } from './AssistantMessage'
import styles from './PlanCard.module.css'

const STATE_CHIPS = {
  pending: { label: 'Awaiting your approval', className: 'chipPending' },
  approved: { label: 'Approved', className: 'chipApproved' },
  changes_requested: { label: 'Changes requested', className: 'chipChanges' },
  expired: { label: 'No longer pending', className: 'chipExpired' },
}

const STEP_ICONS = { completed: 'checkCircle', in_progress: 'refresh' }

/**
 * A proposed plan. While pending, the user can approve it or request changes with feedback.
 * After a decision the card records what was decided, and when.
 */
export default function PlanCard({ plan, onApprove, onRequestChanges, disabled, executing }) {
  const [editing, setEditing] = useState(false)
  const [feedback, setFeedback] = useState('')
  const chip = STATE_CHIPS[plan.state] || STATE_CHIPS.pending
  const isPending = plan.state === 'pending'

  const submitFeedback = (event) => {
    event.preventDefault()
    if (!feedback.trim()) return
    onRequestChanges(feedback.trim())
    setEditing(false)
    setFeedback('')
  }

  return (
    <div className={styles.row}>
      <AssistantAvatar />
      <article className={`${styles.card} ${isPending ? styles.pending : ''}`} aria-label="Proposed plan">
        <header className={styles.header}>
          <span className={styles.icon}>
            <Icon name="list" size={18} />
          </span>
          <div className={styles.titles}>
            <h3 className={styles.title}>{plan.revision > 1 ? `Revised plan · v${plan.revision}` : 'Proposed plan'}</h3>
            {isPending && <p className={styles.subtitle}>Review the steps below. Nothing runs until you approve.</p>}
          </div>
          <span className={`${styles.chip} ${styles[chip.className]}`}>{chip.label}</span>
        </header>

        <ol className={styles.steps}>
          {plan.steps.map((step, index) => (
            <li key={index} className={styles.step}>
              <span className={styles.number}>{index + 1}</span>
              <span className={styles.stepText}>{step.content}</span>
              {STEP_ICONS[step.status] && (
                <span className={styles.stepStatus} title={step.status.replace('_', ' ')}>
                  <Icon name={STEP_ICONS[step.status]} size={15} />
                </span>
              )}
            </li>
          ))}
          {plan.steps.length === 0 && <li className={styles.stepText}>The assistant did not list any steps.</li>}
        </ol>

        <footer className={styles.footer}>
          {isPending && !editing && (
            <div className={styles.actions}>
              <Button variant="outline" icon="edit" onClick={() => setEditing(true)} disabled={disabled}>
                Request changes
              </Button>
              <Button variant="gradient" icon="check" onClick={onApprove} disabled={disabled}>
                Approve &amp; run
              </Button>
            </div>
          )}

          {isPending && editing && (
            <form className={styles.feedback} onSubmit={submitFeedback}>
              <label htmlFor={`feedback-${plan.id}`} className={styles.feedbackLabel}>
                What should change?
              </label>
              <textarea
                id={`feedback-${plan.id}`}
                className={styles.textarea}
                rows={3}
                maxLength={2000}
                autoFocus
                placeholder="e.g. Use Medium priority and check my location first."
                value={feedback}
                onChange={(event) => setFeedback(event.target.value)}
              />
              <div className={styles.actions}>
                <Button variant="ghost" onClick={() => setEditing(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" icon="send" disabled={disabled || !feedback.trim()}>
                  Send feedback
                </Button>
              </div>
            </form>
          )}

          {plan.state === 'approved' && (
            <p className={`${styles.decision} ${styles.approvedText}`}>
              <Icon name="checkCircle" size={16} /> Approved at {timeLabel(new Date(plan.decidedAt))}
              {executing ? ' · executing now…' : ''}
            </p>
          )}

          {plan.state === 'changes_requested' && (
            <div className={styles.decision}>
              <p className={styles.changesText}>
                <Icon name="refresh" size={16} /> Changes requested at {timeLabel(new Date(plan.decidedAt))}
              </p>
              {plan.feedback && <blockquote className={styles.quote}>{plan.feedback}</blockquote>}
            </div>
          )}

          {plan.state === 'expired' && (
            <p className={styles.decision}>
              <Icon name="info" size={16} /> This plan is no longer waiting for a decision.
            </p>
          )}
        </footer>
      </article>
    </div>
  )
}
