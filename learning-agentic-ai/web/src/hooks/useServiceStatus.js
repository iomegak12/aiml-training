import { useCallback, useEffect, useRef, useState } from 'react'
import { getReadiness } from '../services/statusService'

const POLL_MS = 30_000

/** Polls GET /api/ready. status: "loading" | "ready" | "not_ready" | "unreachable". */
export function useServiceStatus() {
  const [state, setState] = useState({ status: 'loading', checks: {}, checkedAt: null })
  const controllerRef = useRef(null)

  const refresh = useCallback(async () => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    try {
      const result = await getReadiness({ signal: controller.signal })
      setState({ status: result.status, checks: result.checks || {}, checkedAt: new Date() })
    } catch (error) {
      if (error.name !== 'AbortError') setState({ status: 'unreachable', checks: {}, checkedAt: new Date() })
    }
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, POLL_MS)
    return () => {
      clearInterval(timer)
      controllerRef.current?.abort()
    }
  }, [refresh])

  return { ...state, refresh }
}
