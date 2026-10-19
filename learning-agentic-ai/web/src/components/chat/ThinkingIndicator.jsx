import { useEffect, useMemo, useState } from 'react'
import { PHASE_TITLES, rotationFor } from '../../content/phrases'
import { useRotatingText } from '../../hooks/useRotatingText'
import styles from './ThinkingIndicator.module.css'

/** Animated orb with rotating phase messages and good-vibe lines while the assistant works. */
export default function ThinkingIndicator({ phase = 'standard', startedAt }) {
  const items = useMemo(() => rotationFor(phase), [phase])
  const { text, index } = useRotatingText(items, 2200, phase)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const tick = () => setElapsed(Math.floor((Date.now() - (startedAt || Date.now())) / 1000))
    tick()
    const timer = setInterval(tick, 1000)
    return () => clearInterval(timer)
  }, [startedAt])

  return (
    <div className={styles.row} role="status" aria-live="polite">
      <div className={styles.orb} aria-hidden="true">
        <span className={styles.halo} />
        <span className={styles.halo2} />
        <span className={styles.core} />
        <span className={styles.shine} />
      </div>
      <div className={styles.text}>
        <span className={styles.phase}>
          {PHASE_TITLES[phase] || 'Thinking'}
          <span className={styles.dots} aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span className={styles.elapsed}>{elapsed}s</span>
        </span>
        <span key={index} className={styles.message}>
          {text}
        </span>
      </div>
    </div>
  )
}
