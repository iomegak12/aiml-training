import { Link } from 'react-router-dom'
import Button from '../components/common/Button'
import { LogoMark } from '../components/common/Logo'
import styles from './NotFoundPage.module.css'

export default function NotFoundPage() {
  return (
    <div className={styles.page}>
      <LogoMark size={64} />
      <h1 className={styles.title}>Page not found</h1>
      <p className={styles.text}>The page you're looking for doesn't exist or has moved.</p>
      <Button as={Link} to="/" variant="gradient" icon="home">
        Back to home
      </Button>
    </div>
  )
}
