import { useEffect, useState } from 'react'

/** Cycles through `items` every `intervalMs`; restarts when `resetKey` changes. */
export function useRotatingText(items, intervalMs = 2200, resetKey = null) {
  const [index, setIndex] = useState(0)

  useEffect(() => {
    setIndex(0)
    if (items.length < 2) return undefined
    const timer = setInterval(() => setIndex((i) => (i + 1) % items.length), intervalMs)
    return () => clearInterval(timer)
  }, [items, intervalMs, resetKey])

  return { text: items[index] || '', index }
}
