import { useEffect, useRef, useState } from 'react'
import { Play, Pause, RotateCcw, X, Check } from 'lucide-react'

const RADIUS = 52
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export function mmss(total) {
  const t = Math.max(0, Math.ceil(total))
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const s = t % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

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
export function useTimers() {
  const [timers, setTimers] = useState({})
  const audioRef = useRef(null)

  useEffect(() => {
    const iv = setInterval(() => {
      setTimers((prev) => {
        const ids = Object.keys(prev)
        if (!ids.length) return prev
        let changed = false
        let justFinished = false
        const next = {}
        for (const id of ids) {
          const t = prev[id]
          if (t.running) {
            const left = (t.endTime - Date.now()) / 1000
            if (left <= 0) {
              next[id] = { ...t, remaining: 0, running: false, done: true }
              justFinished = true
              changed = true
            } else {
              next[id] = { ...t, remaining: left }
              changed = true
            }
          } else {
            next[id] = t
          }
        }
        if (justFinished) {
          playBeeps(audioRef)
          navigator.vibrate?.([200, 100, 200])
        }
        return changed ? next : prev
      })
    }, 250)
    return () => clearInterval(iv)
  }, [])

  const start = (id, seconds, label) =>
    setTimers((p) => {
      const ex = p[id]
      const rem = ex && !ex.done && ex.remaining > 0 ? ex.remaining : seconds
      return {
        ...p,
        [id]: { seconds, label, remaining: rem, running: true, done: false, endTime: Date.now() + rem * 1000 },
      }
    })

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

  return { timers, start, pause, reset, dismiss }
}

/** Big ring for the active step. Reads its state from the shared store by id. */
export function TimerRing({ id, seconds, label, timer, onStart, onPause, onReset }) {
  const remaining = timer ? timer.remaining : seconds
  const running = timer?.running
  const done = timer?.done
  const fresh = !timer || (timer.remaining === timer.seconds && !timer.running && !timer.done)

  const progress = seconds > 0 ? remaining / seconds : 0
  const offset = CIRCUMFERENCE * (1 - Math.min(1, Math.max(0, progress)))

  return (
    <div className={`timer-ring${done ? ' done' : ''}`}>
      <svg viewBox="0 0 120 120" className="timer-svg" aria-hidden="true">
        <circle className="timer-track" cx="60" cy="60" r={RADIUS} />
        <circle
          className="timer-arc"
          cx="60"
          cy="60"
          r={RADIUS}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="timer-time">
        <span className="timer-digits">{done ? 'Done!' : mmss(remaining)}</span>
        {label && !done && <span className="timer-label">{label}</span>}
      </div>

      <div className="timer-controls">
        {done ? (
          <button className="btn ghost" onClick={onReset}>
            <RotateCcw size={15} strokeWidth={2.2} /> Reset
          </button>
        ) : running ? (
          <button className="btn ghost" onClick={onPause}>
            <Pause size={15} strokeWidth={2.2} /> Pause
          </button>
        ) : (
          <button className="btn primary" onClick={onStart}>
            <Play size={15} strokeWidth={2.2} /> {fresh ? 'Start timer' : 'Resume'}
          </button>
        )}
        {!done && !fresh && !running && (
          <button className="btn ghost" onClick={onReset}>
            <RotateCcw size={15} strokeWidth={2.2} /> Reset
          </button>
        )}
      </div>
    </div>
  )
}

/** Compact chip for the persistent bar — a timer started on another step. */
export function TimerChip({ timer, onToggle, onDismiss, onJump }) {
  return (
    <div className={`timer-chip${timer.done ? ' done' : ''}`}>
      <button className="timer-chip-main" onClick={onJump} title="Go to this step">
        {timer.done ? <Check size={14} strokeWidth={2.6} /> : null}
        <span className="timer-chip-time">{timer.done ? 'Done' : mmss(timer.remaining)}</span>
        {timer.label && !timer.done && <span className="timer-chip-label">{timer.label}</span>}
      </button>
      {!timer.done && (
        <button className="timer-chip-btn" onClick={onToggle} aria-label={timer.running ? 'Pause' : 'Resume'}>
          {timer.running ? <Pause size={13} strokeWidth={2.4} /> : <Play size={13} strokeWidth={2.4} />}
        </button>
      )}
      <button className="timer-chip-btn" onClick={onDismiss} aria-label="Dismiss timer">
        <X size={13} strokeWidth={2.4} />
      </button>
    </div>
  )
}
