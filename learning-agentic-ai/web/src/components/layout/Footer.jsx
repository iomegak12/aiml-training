import { Link } from 'react-router-dom'
import { API_BASE } from '../../services/apiClient'
import styles from './Footer.module.css'

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <span>© {new Date().getFullYear()} Corvana Networks · Demo application</span>
      <nav className={styles.links} aria-label="Footer">
        <Link to="/support">Support</Link>
        <Link to="/contact">Contact</Link>
        <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
          API docs
        </a>
      </nav>
    </footer>
  )
}
