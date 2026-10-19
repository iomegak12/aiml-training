import { Link, NavLink } from 'react-router-dom'
import Icon from '../common/Icon'
import { Logo } from '../common/Logo'
import StatusBell from './StatusBell'
import Avatar from './Avatar'
import styles from './NavBar.module.css'

const LINKS = [
  { to: '/', label: 'Home', icon: 'home', end: true },
  { to: '/support', label: 'Support', icon: 'sparkles' },
  { to: '/contact', label: 'Contact Us', icon: 'mail' },
]

export default function NavBar() {
  return (
    <header className={styles.bar}>
      <Link to="/" className={styles.brand} aria-label="Corvana Networks home">
        <Logo />
      </Link>

      <nav className={styles.nav} aria-label="Main">
        {LINKS.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.end}
            className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
          >
            <span className={styles.linkIcon}>
              <Icon name={link.icon} size={17} />
            </span>
            <span className={styles.linkLabel}>{link.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className={styles.actions}>
        <StatusBell />
        <Avatar />
      </div>
    </header>
  )
}
