import Icon from '../common/Icon'
import styles from './ReasoningPanel.module.css'

/** Collapsible reasoning summary streamed by the model. */
export default function ReasoningPanel({ text, live }) {
  return (
    <details className={styles.panel}>
      <summary className={styles.summary}>
        <Icon name="brain" size={15} />
        <span>{live ? 'Reasoning…' : 'Reasoning'}</span>
        {live && <span className={styles.live} aria-hidden="true" />}
        <Icon name="chevronDown" size={15} className={styles.chevron} />
      </summary>
      <p className={styles.text}>{text}</p>
    </details>
  )
}
