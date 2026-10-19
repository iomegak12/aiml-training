import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'
import Icon from '../common/Icon'
import styles from './ChatInput.module.css'

const MAX_LENGTH = 8000

/** "Ask anything…" input with Send. Enter sends, Shift+Enter adds a new line. */
const ChatInput = forwardRef(function ChatInput({ value, onChange, onSend, disabled, hint }, ref) {
  const textareaRef = useRef(null)
  useImperativeHandle(ref, () => ({ focus: () => textareaRef.current?.focus() }))

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [value])

  const canSend = !disabled && value.trim().length > 0

  const submit = (event) => {
    event.preventDefault()
    if (canSend) onSend()
  }

  return (
    <form className={styles.wrapper} onSubmit={submit}>
      {hint && (
        <p className={styles.hint} role="status">
          <Icon name="info" size={15} /> {hint}
        </p>
      )}
      <div className={`${styles.bar} ${disabled ? styles.locked : ''}`}>
        <textarea
          ref={textareaRef}
          className={styles.input}
          rows={1}
          maxLength={MAX_LENGTH}
          placeholder="Ask anything ..."
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) submit(event)
          }}
          aria-label="Message"
        />
        <button type="submit" className={styles.send} disabled={!canSend}>
          Send <Icon name="arrowUpRight" size={18} />
        </button>
      </div>
    </form>
  )
})

export default ChatInput
