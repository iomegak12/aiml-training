const SAME_DAY = (a, b) => a.toDateString() === b.toDateString()

function ordinal(day) {
  if (day % 100 >= 11 && day % 100 <= 13) return 'th'
  return { 1: 'st', 2: 'nd', 3: 'rd' }[day % 10] || 'th'
}

/** Group label for the history list: "Today" or "12th June, 2023" (as parts for <sup>). */
export function dayLabel(date, now = new Date()) {
  if (SAME_DAY(date, now)) return { text: 'Today' }
  const day = date.getDate()
  const month = date.toLocaleDateString('en-GB', { month: 'long' })
  return { day, suffix: ordinal(day), rest: `${month}, ${date.getFullYear()}` }
}

export function timeLabel(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function truncate(text, max = 48) {
  const clean = text.replace(/\s+/g, ' ').trim()
  return clean.length > max ? `${clean.slice(0, max - 1).trimEnd()}…` : clean
}

/** Friendly label for a tool name, e.g. "register_ticket" -> "Register ticket". */
export function toolLabel(name = '') {
  const label = name.replace(/_/g, ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

let counter = 0
export function uid(prefix = 'id') {
  counter += 1
  return `${prefix}-${Date.now().toString(36)}-${counter}`
}
