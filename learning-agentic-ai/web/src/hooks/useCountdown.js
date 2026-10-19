import { useEffect, useState } from 'react'

/** Whole seconds remaining until `untilMs` (epoch ms); 0 when passed or null. */
export function useCountdown(untilMs) {
  const remaining = () => (untilMs ? Math.max(0, Math.ceil((untilMs - Date.now()) / 1000)) : 0)
  const [seconds, setSeconds] = useState(remaining)

  useEffect(() => {
    setSeconds(remaining())
    if (!untilMs) return undefined
    const timer = setInterval(() => {
      const next = remaining()
      setSeconds(next)
      if (next === 0) clearInterval(timer)
    }, 250)
    return () => clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [untilMs])

  return seconds
}
