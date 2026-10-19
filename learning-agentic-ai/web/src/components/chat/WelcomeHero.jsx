import { LogoMark } from '../common/Logo'
import styles from './WelcomeHero.module.css'

export default function WelcomeHero() {
  return (
    <div className={styles.hero}>
      <div className={styles.tile}>
        <LogoMark size={58} />
      </div>
      <h1 className={styles.title}>
        Welcome to the <span className={styles.brand}>Corvana</span>
      </h1>
      <p className={styles.subtitle}>Your AI Support Assistant</p>
    </div>
  )
}
