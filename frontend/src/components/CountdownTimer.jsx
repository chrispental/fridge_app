import { Play, Pause, RotateCcw, X, Check } from 'lucide-react'

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

/** Big ring for the active step. Reads its state from the shared store by id. */
export function TimerRing({ seconds, label, timer, onStart, onPause, onReset }) {
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
