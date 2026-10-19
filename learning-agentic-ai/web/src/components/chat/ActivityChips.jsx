import Icon from '../common/Icon'
import { toolLabel } from '../../utils/format'
import styles from './ActivityChips.module.css'

const STATUS = {
  running: { label: 'Running', icon: null },
  done: { label: 'Done', icon: 'check' },
  error: { label: 'Returned an error', icon: 'alert' },
  stopped: { label: 'Stopped', icon: 'x' },
}

/** Live tool activity: one chip per tool call, e.g. "Get weather ✓". */
export default function ActivityChips({ items }) {
  return (
    <ul className={styles.chips} aria-label="Tool activity">
      {items.map((item) => {
        const status = STATUS[item.status] || STATUS.running
        return (
          <li
            key={item.id}
            className={`${styles.chip} ${styles[item.status]}`}
            title={`${item.name}(${JSON.stringify(item.args ?? {})})`}
          >
            <Icon name="wrench" size={14} />
            <span>
              {item.status === 'running' ? 'Using ' : ''}
              {toolLabel(item.name)}
              {item.subagent ? ' (subagent)' : ''}
            </span>
            {item.status === 'running' ? (
              <span className={styles.spinner} aria-label={status.label} />
            ) : (
              <span className={styles.statusIcon} aria-label={status.label}>
                <Icon name={status.icon} size={13} strokeWidth={2.4} />
              </span>
            )}
          </li>
        )
      })}
    </ul>
  )
}
