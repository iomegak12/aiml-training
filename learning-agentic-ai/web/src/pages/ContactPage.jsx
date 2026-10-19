import { useState } from 'react'
import { Link } from 'react-router-dom'
import Button from '../components/common/Button'
import Icon from '../components/common/Icon'
import { CONTACT_CARDS, CONTACT_EMAIL, SUBJECTS } from '../content/contact'
import styles from './ContactPage.module.css'

const EMPTY_FORM = { name: '', email: '', subject: SUBJECTS[0], message: '' }

function validate(form) {
  const errors = {}
  if (!form.name.trim()) errors.name = 'Please enter your name.'
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) errors.email = 'Please enter a valid email address.'
  if (form.message.trim().length < 10) errors.message = 'Please write at least 10 characters.'
  return errors
}

/** Contact details and a form that opens the visitor's email app (mailto:) with the message prefilled. */
export default function ContactPage() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [errors, setErrors] = useState({})
  const [opened, setOpened] = useState(false)

  const update = (field) => (event) => setForm((current) => ({ ...current, [field]: event.target.value }))

  const submit = (event) => {
    event.preventDefault()
    const found = validate(form)
    setErrors(found)
    if (Object.keys(found).length) return

    const subject = `[${form.subject}] Message from ${form.name.trim()}`
    const body = `${form.message.trim()}\n\n--\n${form.name.trim()}\n${form.email.trim()}`
    window.location.href = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
    setOpened(true)
  }

  return (
    <div className={styles.page}>
      <section className={styles.intro}>
        <span className={styles.eyebrow}>Contact us</span>
        <h1 className={styles.title}>
          We'd love to <span className={styles.highlight}>hear from you</span>
        </h1>
        <p className={styles.subtitle}>
          Questions about Corvana Networks or the AI assistant? Reach out, or try the{' '}
          <Link to="/support">AI Support assistant</Link> for instant help.
        </p>
      </section>

      <div className={styles.grid}>
        <div className={styles.cards}>
          {CONTACT_CARDS.map((card) => (
            <article key={card.title} className={styles.card}>
              <span className={styles.cardIcon}>
                <Icon name={card.icon} size={20} />
              </span>
              <div>
                <h2 className={styles.cardTitle}>{card.title}</h2>
                {card.lines.map((line, index) =>
                  index === 0 && card.href ? (
                    <a key={line} href={card.href} className={styles.cardLine}>
                      {line}
                    </a>
                  ) : (
                    <p key={line} className={styles.cardLine}>
                      {line}
                    </p>
                  ),
                )}
              </div>
            </article>
          ))}
          <p className={styles.demoNote}>
            <Icon name="info" size={15} /> Demo placeholder details: replace them before going live.
          </p>
        </div>

        <form className={styles.form} onSubmit={submit} noValidate>
          <h2 className={styles.formTitle}>Send us a message</h2>
          <p className={styles.formText}>Sending opens your email app with everything filled in.</p>

          <div className={styles.row}>
            <label className={styles.field}>
              <span>Name</span>
              <input value={form.name} onChange={update('name')} autoComplete="name" aria-invalid={Boolean(errors.name)} />
              {errors.name && <span className={styles.error}>{errors.name}</span>}
            </label>
            <label className={styles.field}>
              <span>Email</span>
              <input
                type="email"
                value={form.email}
                onChange={update('email')}
                autoComplete="email"
                aria-invalid={Boolean(errors.email)}
              />
              {errors.email && <span className={styles.error}>{errors.email}</span>}
            </label>
          </div>

          <label className={styles.field}>
            <span>Subject</span>
            <select value={form.subject} onChange={update('subject')}>
              {SUBJECTS.map((subject) => (
                <option key={subject}>{subject}</option>
              ))}
            </select>
          </label>

          <label className={styles.field}>
            <span>Message</span>
            <textarea rows={6} value={form.message} onChange={update('message')} aria-invalid={Boolean(errors.message)} />
            {errors.message && <span className={styles.error}>{errors.message}</span>}
          </label>

          <div className={styles.formFooter}>
            {opened && (
              <span className={styles.success} role="status">
                <Icon name="checkCircle" size={16} /> Your email app should open now. Didn't? Write to {CONTACT_EMAIL}.
              </span>
            )}
            <Button type="submit" variant="primary" iconRight="send">
              Send message
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}
