import styles from './Messages.module.css'

const MODE_LABELS = { plan: 'Plan first', streaming: 'Streaming', standard: 'Standard' }

export default function UserMessage({ message }) {
  return (
    <div className={`${styles.row} ${styles.userRow}`}>
      <div className={styles.userBubble}>
        <p className={styles.userText}>{message.content}</p>
        <span className={styles.userMeta}>{MODE_LABELS[message.mode]}</span>
      </div>
    </div>
  )
}
