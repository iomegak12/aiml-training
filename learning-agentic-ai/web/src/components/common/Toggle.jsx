import styles from './Toggle.module.css'

/** Labelled on/off switch. `hint` is shown as a tooltip. */
export default function Toggle({ label, checked, onChange, disabled = false, hint }) {
  return (
    <label className={`${styles.toggle} ${disabled ? styles.disabled : ''}`} title={hint}>
      <input
        type="checkbox"
        role="switch"
        className={styles.input}
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        aria-label={label}
      />
      <span className={styles.track} aria-hidden="true">
        <span className={styles.thumb} />
      </span>
      <span className={styles.label}>{label}</span>
    </label>
  )
}
