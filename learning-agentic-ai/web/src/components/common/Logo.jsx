import { useId } from 'react'
import styles from './Logo.module.css'

// Corvana Networks brand: a "C" formed by a network arc with connected nodes,
// in the reference design's cyan -> indigo -> magenta -> pink gradient.

function GradientDefs({ id }) {
  return (
    <defs>
      <linearGradient id={id} x1="4" y1="6" x2="44" y2="42" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#22d3ee" />
        <stop offset="0.38" stopColor="#6366f1" />
        <stop offset="0.72" stopColor="#c026d3" />
        <stop offset="1" stopColor="#f472b6" />
      </linearGradient>
    </defs>
  )
}

function MarkShapes({ fill }) {
  return (
    <>
      <path d="M33.9 14.1 A14 14 0 1 0 33.9 33.9" fill="none" stroke={fill} strokeWidth="5.5" strokeLinecap="round" />
      <path d="M33.9 14.1 L25 24 L33.9 33.9" fill="none" stroke={fill} strokeWidth="1.8" opacity="0.7" />
      <circle cx="33.9" cy="14.1" r="3.6" fill={fill} />
      <circle cx="33.9" cy="33.9" r="3.6" fill={fill} />
      <circle cx="25" cy="24" r="2.8" fill={fill} />
    </>
  )
}

/** The "C" network mark on its own. */
export function LogoMark({ size = 36, solid = null }) {
  const id = useId()
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      {!solid && <GradientDefs id={id} />}
      <MarkShapes fill={solid || `url(#${id})`} />
    </svg>
  )
}

/** Mark + "corvana / NETWORKS" wordmark, as in the header. */
export function Logo({ compact = false }) {
  return (
    <span className={styles.logo}>
      <LogoMark size={40} />
      {!compact && (
        <span className={styles.wordmark}>
          <span className={styles.name}>corvana</span>
          <span className={styles.tagline}>networks</span>
        </span>
      )}
      <span className="visually-hidden">Corvana Networks</span>
    </span>
  )
}

/** Scalloped gradient badge with a white tile and the mark (the round badge in the chat card). */
export function LogoBadge({ size = 76 }) {
  const id = useId()
  const lobes = 9
  const points = Array.from({ length: 144 }, (_, i) => {
    const angle = (i / 144) * Math.PI * 2
    const radius = 22 + 1.8 * Math.cos(lobes * angle)
    return `${(24 + radius * Math.cos(angle)).toFixed(2)},${(24 + radius * Math.sin(angle)).toFixed(2)}`
  })
  return (
    <svg className={styles.badge} width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <GradientDefs id={id} />
      <g className={styles.petals}>
        <polygon points={points.join(' ')} fill={`url(#${id})`} />
      </g>
      <rect x="13" y="13" width="22" height="22" rx="6.5" fill="#fff" />
      <g transform="translate(15.2 15.2) scale(0.36)">
        <MarkShapes fill={`url(#${id})`} />
      </g>
    </svg>
  )
}
