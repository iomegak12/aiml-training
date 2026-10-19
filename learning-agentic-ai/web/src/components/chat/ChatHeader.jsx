import Toggle from '../common/Toggle'
import { LogoBadge } from '../common/Logo'
import styles from './ChatHeader.module.css'

function modeDescription({ streaming, planFirst }) {
  if (planFirst) return 'Plan first: review and approve the steps before anything runs'
  return streaming ? 'Streaming: watch the assistant think and work live' : 'Standard: the complete answer arrives at once'
}

/** Chat card header: title, Streaming / Plan first switches and the round brand badge. */
export default function ChatHeader({ settings, onChange }) {
  const { streaming, planFirst } = settings

  return (
    <header className={styles.header}>
      <div className={styles.titles}>
        <h2 className={styles.title}>AI Support Assistant</h2>
        <p className={styles.subtitle}>{modeDescription(settings)}</p>
      </div>

      <div className={styles.controls}>
        <Toggle
          label="Streaming"
          checked={streaming && !planFirst}
          disabled={planFirst}
          onChange={(value) => onChange({ streaming: value })}
          hint={planFirst ? 'Plan mode uses standard responses' : 'Stream reasoning, tool activity and the answer live'}
        />
        <Toggle
          label="Plan first"
          checked={planFirst}
          onChange={(value) => onChange({ planFirst: value })}
          hint="The assistant proposes a plan and waits for your approval. Plan conversations keep their own memory."
        />
      </div>

      <div className={styles.badge}>
        <LogoBadge size={72} />
      </div>
    </header>
  )
}
