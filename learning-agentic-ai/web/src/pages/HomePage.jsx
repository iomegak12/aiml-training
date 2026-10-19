import { Link } from 'react-router-dom'
import Button from '../components/common/Button'
import Icon from '../components/common/Icon'
import { LogoBadge } from '../components/common/Logo'
import SectionHeading from '../components/home/SectionHeading'
import { API_BASE } from '../services/apiClient'
import { ENDPOINTS, FEATURES, FLOW, HERO, LIFECYCLE, TOOLS } from '../content/home'
import styles from './HomePage.module.css'

export default function HomePage() {
  return (
    <div className={styles.page}>
      {/* Hero */}
      <section className={`${styles.card} ${styles.hero}`}>
        <div className={styles.heroText}>
          <span className={styles.eyebrow}>
            <Icon name="sparkles" size={15} /> {HERO.eyebrow}
          </span>
          <h1 className={styles.heroTitle}>
            {HERO.title} <span className={styles.gradientText}>{HERO.highlight}</span>
          </h1>
          <p className={styles.heroSubtitle}>{HERO.subtitle}</p>
          <div className={styles.heroActions}>
            <Button as={Link} to="/support" variant="gradient" size="lg" iconRight="arrowRight">
              Talk to the assistant
            </Button>
            <Button as="a" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer" variant="outline" size="lg" icon="server">
              Explore the API
            </Button>
          </div>
        </div>
        <div className={styles.heroArt} aria-hidden="true">
          <LogoBadge size={210} />
          <span className={`${styles.floatChip} ${styles.chipOne}`}>
            <Icon name="ticket" size={15} /> TKT-00042 resolved
          </span>
          <span className={`${styles.floatChip} ${styles.chipTwo}`}>
            <Icon name="list" size={15} /> Plan approved
          </span>
          <span className={`${styles.floatChip} ${styles.chipThree}`}>
            <Icon name="zap" size={15} /> Streaming live
          </span>
        </div>
      </section>

      {/* Features */}
      <section className={styles.section}>
        <SectionHeading eyebrow="What it does" title="An assistant that works the ticket desk with you" />
        <div className={styles.features}>
          {FEATURES.map((feature) => (
            <article key={feature.title} className={`${styles.card} ${styles.feature}`}>
              <span className={styles.featureIcon}>
                <Icon name={feature.icon} size={20} />
              </span>
              <h3 className={styles.featureTitle}>{feature.title}</h3>
              <p className={styles.featureText}>{feature.text}</p>
            </article>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className={styles.section}>
        <SectionHeading eyebrow="How it works" title="From your message to a resolved ticket" />
        <ol className={styles.flow}>
          {FLOW.map((step, index) => (
            <li key={step.title} className={`${styles.card} ${styles.flowStep}`}>
              <span className={styles.flowNumber}>{index + 1}</span>
              <span className={styles.flowIcon}>
                <Icon name={step.icon} size={22} />
              </span>
              <h3 className={styles.flowTitle}>{step.title}</h3>
              <p className={styles.flowText}>{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Tools + lifecycle */}
      <section className={`${styles.section} ${styles.split}`}>
        <article className={`${styles.card} ${styles.panel}`}>
          <h3 className={styles.panelTitle}>
            <Icon name="wrench" size={18} /> Agent tools
          </h3>
          <p className={styles.panelText}>Ticket tools wrap the ticket library; local tools add context.</p>
          <div className={styles.toolGroup}>
            <span className={styles.toolLabel}>Tickets</span>
            {TOOLS.tickets.map((tool) => (
              <code key={tool}>{tool}</code>
            ))}
          </div>
          <div className={styles.toolGroup}>
            <span className={styles.toolLabel}>Local</span>
            {TOOLS.local.map((tool) => (
              <code key={tool}>{tool}</code>
            ))}
          </div>
        </article>

        <article className={`${styles.card} ${styles.panel}`}>
          <h3 className={styles.panelTitle}>
            <Icon name="ticket" size={18} /> Ticket lifecycle
          </h3>
          <p className={styles.panelText}>Resolved tickets are archived and disappear from searches.</p>
          <div className={styles.lifecycle}>
            {LIFECYCLE.map((status, index) => (
              <span key={status} className={styles.lifecycleStep}>
                <span className={styles.status}>{status}</span>
                {index < LIFECYCLE.length - 1 && <Icon name="arrowRight" size={16} />}
              </span>
            ))}
          </div>
          <p className={styles.panelNote}>Priorities: Low · Medium · High · Critical</p>
        </article>
      </section>

      {/* API */}
      <section className={styles.section}>
        <SectionHeading eyebrow="For developers" title="A clean REST API behind the scenes" />
        <div className={`${styles.card} ${styles.tableCard}`}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Method</th>
                <th scope="col">Endpoint</th>
                <th scope="col">What it does</th>
              </tr>
            </thead>
            <tbody>
              {ENDPOINTS.map((endpoint) => (
                <tr key={endpoint.path}>
                  <td>
                    <span className={`${styles.method} ${styles[endpoint.method.toLowerCase()]}`}>{endpoint.method}</span>
                  </td>
                  <td>
                    <code>/api{endpoint.path}</code>
                  </td>
                  <td>{endpoint.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className={styles.tableNote}>
            <Icon name="shield" size={16} /> 100 requests per minute per client, then a 30-second pause · Errors as RFC 9457
            Problem Details with a request ID · Interactive docs at{' '}
            <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
              /api/docs
            </a>
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className={`${styles.card} ${styles.cta}`}>
        <div>
          <h2 className={styles.ctaTitle}>Ready to clear your ticket queue?</h2>
          <p className={styles.ctaText}>Try a suggested prompt or describe your issue in your own words.</p>
        </div>
        <Button as={Link} to="/support" variant="primary" size="lg" iconRight="arrowUpRight">
          Open AI Support
        </Button>
      </section>
    </div>
  )
}
