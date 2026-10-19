import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { LogoMark } from '../common/Logo'
import ActivityChips from './ActivityChips'
import ReasoningPanel from './ReasoningPanel'
import styles from './Messages.module.css'

const MARKDOWN_COMPONENTS = {
  a: ({ node, ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
}

export function AssistantAvatar() {
  return (
    <span className={styles.assistantAvatar} aria-hidden="true">
      <LogoMark size={22} />
    </span>
  )
}

/** Assistant reply: tool activity, reasoning summary and Markdown answer (streams in live). */
export default function AssistantMessage({ message }) {
  const { content, activity = [], reasoning, streaming } = message

  return (
    <div className={styles.row}>
      <AssistantAvatar />
      <div className={styles.assistantBubble} aria-busy={streaming || undefined}>
        {activity.length > 0 && <ActivityChips items={activity} />}
        {reasoning && <ReasoningPanel text={reasoning} live={streaming && !content} />}
        {content ? (
          <div className={styles.markdown}>
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
              {content}
            </ReactMarkdown>
            {streaming && <span className={styles.caret} aria-hidden="true" />}
          </div>
        ) : streaming ? (
          <p className={styles.working}>Working on it…</p>
        ) : (
          <p className={styles.working}>The assistant finished without a text reply.</p>
        )}
      </div>
    </div>
  )
}
