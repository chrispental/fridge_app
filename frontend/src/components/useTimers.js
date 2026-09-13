import { useContext, useEffect, useRef, useState } from 'react'
import { readStored, writeStored } from '../utils/storage.js'
import { TimerContext } from './timerContext.js'

// One short oscillator chime. Lazily creates the AudioContext (unlocked by the user's
// first Start tap) and is fully best-effort — any failure is swallowed.
function playBeeps(ctxRef) {
  try {
    if (!ctxRef.current) {
      const Ctx = window.AudioContext || window.webkitAudioContext
      if (!Ctx) return
      ctxRef.current = new Ctx()
    }
    const ctx = ctxRef.current
    const now = ctx.currentTime
    for (let i = 0; i < 3; i++) {
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      const start = now + i * 0.28
      osc.frequency.value = 880
      osc.type = 'sine'
      gain.gain.setValueAtTime(0, start)
      gain.gain.linearRampToValueAtTime(0.18, start + 0.02)
      gain.gain.linearRampToValueAtTime(0, start + 0.18)
      osc.connect(gain).connect(ctx.destination)
      osc.start(start)
      osc.stop(start + 0.2)
    }
  } catch {
    /* audio is a nicety, never block on it */
  }
}

/**
 * Shared timer store. One interval drives every timer, so countdowns keep running
 * after you navigate away from the step that started them. Timers are clock-based
 * (`endTime`) so they don't drift when the tab is backgrounded.
 */
export function useTimerStore(storageKey) {
  const [timers, setTimers] = useState(() => {
    const saved = readStored(storageKey, {})
    if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return {}
    return Object.fromEntries(Object.entries(saved).filter(([, t]) => t && Number.isFinite(t.seconds) && Number.isFinite(t.remaining) && Number.isFinite(t.endTime)))
  })
  const audioRef = useRef(null)
  const alerted = useRef(new Set())
  useEffect(() => { writeStored(storageKey, timers) }, [storageKey, timers])
  useEffect(() => {
    const newlyDone = Object.entries(timers).filter(([id, t]) => t.done && !alerted.current.has(id))
    if (newlyDone.length) {
      newlyDone.forEach(([id]) => alerted.current.add(id))
      playBeeps(audioRef)
      navigator.vibrate?.([200, 100, 200])
    }
  }, [timers])
  useEffect(() => () => { audioRef.current?.close?.().catch(() => {}) }, [])

  useEffect(() => {
    const iv = setInterval(() => {
      setTimers((prev) => {
        const ids = Object.keys(prev)
        if (!ids.length) return prev
        let changed = false
        const next = {}
        for (const id of ids) {
          const t = prev[id]
          if (t.running) {
            const left = (t.endTime - Date.now()) / 1000
            if (left <= 0) {
              next[id] = { ...t, remaining: 0, running: false, done: true }
              changed = true
            } else {
              next[id] = { ...t, remaining: left }
              changed = true
            }
          } else {
            next[id] = t
          }
        }
        return changed ? next : prev
      })
    }, 250)
    return () => clearInterval(iv)
  }, [])

  const start = (id, seconds, label) => {
    // Unlock sound during the user's tap, not later inside a timer callback.
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext
      if (!audioRef.current && Ctx) audioRef.current = new Ctx()
      audioRef.current?.resume?.().catch(() => {})
    } catch { /* Visual countdowns still work without audio. */ }
    alerted.current.delete(id)
    setTimers((p) => {
      const ex = p[id]
      const rem = ex && !ex.done && ex.remaining > 0 ? ex.remaining : seconds
      return {
        ...p,
        [id]: { seconds, label, remaining: rem, running: true, done: false, endTime: Date.now() + rem * 1000 },
      }
    })
  }

  const pause = (id) =>
    setTimers((p) => {
      const t = p[id]
      if (!t) return p
      const rem = Math.max(0, (t.endTime - Date.now()) / 1000)
      return { ...p, [id]: { ...t, running: false, remaining: rem } }
    })

  const reset = (id, seconds) =>
    setTimers((p) => {
      const t = p[id]
      const s = seconds ?? t?.seconds ?? 0
      return { ...p, [id]: { seconds: s, label: t?.label, remaining: s, running: false, done: false, endTime: 0 } }
    })

  const dismiss = (id) =>
    setTimers((p) => {
      const n = { ...p }
      delete n[id]
      return n
    })

  const clear = (prefix) => setTimers((prev) => Object.fromEntries(Object.entries(prev).filter(([id]) => !id.startsWith(prefix))))
  return { timers, start, pause, reset, dismiss, clear }
}

export function useTimers(storageKey) {
  const store = useContext(TimerContext)
  const prefix = `${storageKey}:`
  const timers = Object.fromEntries(Object.entries(store.timers)
    .filter(([id]) => id.startsWith(prefix)).map(([id, timer]) => [id.slice(prefix.length), timer]))
  return {
    timers,
    start: (id, ...args) => store.start(prefix + id, ...args),
    pause: (id) => store.pause(prefix + id),
    reset: (id, ...args) => store.reset(prefix + id, ...args),
    dismiss: (id) => store.dismiss(prefix + id),
    clear: () => store.clear(prefix),
  }
}
