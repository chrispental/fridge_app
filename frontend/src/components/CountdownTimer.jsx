import { useEffect, useRef, useState, useCallback } from 'react'
import { Play, Pause, RotateCcw } from 'lucide-react'

const RADIUS = 52
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

function mmss(total) {
  const t = Math.max(0, Math.ceil(total))
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const s = t % 60
  const pad = (n) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

// One short oscillator beep. Lazily creates the AudioContext (unlocked by the user's
// Start tap) and is fully best-effort — any failure is swallowed.
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

export default function CountdownTimer({ seconds, label }) {
  const [remaining, setRemaining] = useState(seconds)
  const [running, setRunning] = useState(false)
  const [done, setDone] = useState(false)
  const endRef = useRef(0) // wall-clock target, so backgrounding doesn't drift
  const intervalRef = useRef(null)
  const audioRef = useRef(null)

  const stopTicking = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  useEffect(() => stopTicking, [stopTicking])

  function start() {
    if (done) return
    endRef.current = Date.now() + remaining * 1000
    setRunning(true)
    stopTicking()
    intervalRef.current = setInterval(() => {
      const left = (endRef.current - Date.now()) / 1000
      if (left <= 0) {
        stopTicking()
        setRemaining(0)
        setRunning(false)
        setDone(true)
        playBeeps(audioRef)
        navigator.vibrate?.([200, 100, 200])
      } else {
        setRemaining(left)
      }
    }, 250)
  }

  function pause() {
    stopTicking()
    setRunning(false)
    setRemaining((r) => Math.max(0, (endRef.current - Date.now()) / 1000) || r)
  }

  function reset() {
    stopTicking()
    setRunning(false)
    setDone(false)
    setRemaining(seconds)
  }

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
          <button className="btn ghost" onClick={reset}>
            <RotateCcw size={15} strokeWidth={2.2} /> Reset
          </button>
        ) : running ? (
          <button className="btn ghost" onClick={pause}>
            <Pause size={15} strokeWidth={2.2} /> Pause
          </button>
        ) : (
          <button className="btn primary" onClick={start}>
            <Play size={15} strokeWidth={2.2} /> {remaining < seconds ? 'Resume' : 'Start timer'}
          </button>
        )}
        {!done && remaining < seconds && !running && (
          <button className="btn ghost" onClick={reset}>
            <RotateCcw size={15} strokeWidth={2.2} /> Reset
          </button>
        )}
      </div>
    </div>
  )
}
