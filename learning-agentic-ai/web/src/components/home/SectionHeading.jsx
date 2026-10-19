import styles from './SectionHeading.module.css'

export default function SectionHeading({ eyebrow, title }) {
  return (
    <div className={styles.heading}>
      <span className={styles.eyebrow}>{eyebrow}</span>
      <h2 className={styles.title}>{title}</h2>
    </div>
  )
}
