import Icon from '../common/Icon'
import { SUGGESTIONS } from '../../content/suggestions'
import styles from './SuggestionCards.module.css'

/** Starter prompts for an empty chat. Picking one fills the input (it is not sent automatically). */
export default function SuggestionCards({ onPick }) {
  return (
    <div className={styles.cards}>
      {SUGGESTIONS.map((suggestion) => (
        <button key={suggestion.id} type="button" className={styles.card} onClick={() => onPick(suggestion)}>
          <span className={styles.icon}>
            <Icon name={suggestion.icon} size={20} />
          </span>
          <span className={styles.title}>{suggestion.title}</span>
          <span className={styles.subtitle}>{suggestion.subtitle}</span>
        </button>
      ))}
    </div>
  )
}
