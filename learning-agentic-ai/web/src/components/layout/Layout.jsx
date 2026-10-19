import { Outlet } from 'react-router-dom'
import NavBar from './NavBar'
import Footer from './Footer'
import styles from './Layout.module.css'

export default function Layout() {
  return (
    <div className={styles.shell}>
      <NavBar />
      <main className={styles.main}>
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
