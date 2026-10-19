import Icon from '../common/Icon'
import styles from './Avatar.module.css'

/** Generic user avatar with the brand gradient ring. */
export default function Avatar() {
  return (
    <span className={styles.avatar} title="Guest user" role="img" aria-label="Guest user">
      <span className={styles.inner}>
        <Icon name="user" size={22} />
      </span>
    </span>
  )
}
