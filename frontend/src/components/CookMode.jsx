import { useEffect, useMemo, useRef, useState } from 'react'
import {
  X, ChevronLeft, ChevronRight, Check, ChefHat, PartyPopper, Clock,
} from 'lucide-react'
import { useTimers, TimerRing, TimerChip } from './CountdownTimer.jsx'
import { parseStepDurations, MAX_TIMER_SECONDS } from '../utils/parseStepDuration.js'

const CONFETTI_COLORS = ['#f5a524', '#ffbc52', '#4ade80', '#60a5fa', '#f472b6', '#faf7f3']

function buildConfetti(n) {
  return Array.from({ length: n }, (_, i) => ({
    id: i,
    left: Math.random() * 100,
    delay: Math.random() * 0.5,
    duration: 1 + Math.random() * 0.8,
    rotate: Math.random() * 360,
    color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
  }))
}

const prefersReducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// Timer id for the di-th duration of step stepIdx (0-based step).
const tid = (stepIdx, di) => `s${stepIdx}-${di}`

export default function CookMode({ meal, onClose, onCook }) {
  const recipe = meal.recipe_json || {}
  const steps = recipe.steps || []
  const ingredients = recipe.ingredients || []

  // Slides: [mise en place] + [...steps] + [finish]
  const total = steps.length + 2
  const finishIndex = total - 1
  const [index, setIndex] = useState(0)
  const [direction, setDirection] = useState(1)

  const [decrement, setDecrement] = useState(true)
  const [cooked, setCooked] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [checked, setChecked] = useState(() => new Set())

  const { timers, start, pause, reset, dismiss } = useTimers()

  const isMise = index === 0
  const isFinish = index === finishIndex
  const stepIdx = index - 1 // valid only on step slides
  const stepText = !isMise && !isFinish ? steps[stepIdx] : null

  const durs = useMemo(() => (stepText ? parseStepDurations(stepText) : []), [stepText])

  const go = (dir) => {
    setDirection(dir)
    setIndex((i) => Math.min(finishIndex, Math.max(0, i + dir)))
  }

  // Keyboard navigation + Escape to close.
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'ArrowRight') go(1)
      else if (e.key === 'ArrowLeft') go(-1)
      else if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finishIndex])

  // Lock body scroll while the overlay is open.
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [])

  // Keep the screen awake while cooking. Wake locks drop when the tab is hidden, so
  // re-acquire on visibility change.
  useEffect(() => {
    let lock = null
    let cancelled = false
    const acquire = async () => {
      try {
        lock = (await navigator.wakeLock?.request('screen')) || null
      } catch {
        /* unsupported or denied — harmless */
      }
    }
    acquire()
    const onVis = () => {
      if (document.visibilityState === 'visible' && !cancelled) acquire()
    }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', onVis)
      lock?.release?.().catch(() => {})
    }
  }, [])

  // Swipe handling.
  const swipeX = useRef(0)
  function onPointerDown(e) {
    swipeX.current = e.clientX
  }
  function onPointerUp(e) {
    const dx = e.clientX - swipeX.current
    if (Math.abs(dx) > 50) go(dx < 0 ? 1 : -1)
  }

  async function markCooked() {
    setBusy(true)
    setError(null)
    try {
      await onCook(decrement)
      setCooked(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  function toggleChecked(i) {
    setChecked((cur) => {
      const next = new Set(cur)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  const confetti = useMemo(
    () => (isFinish && !prefersReducedMotion ? buildConfetti(36) : []),
    [isFinish],
  )

  // Persistent timer bar: any running/finished timer that didn't originate on this step.
  const otherTimers = Object.entries(timers)
    .filter(([id]) => !id.startsWith(`s${stepIdx}-`))
    .map(([id, t]) => ({ id, t, jump: Number(id.slice(1).split('-')[0]) + 1 }))

  const progressPct = (index / finishIndex) * 100
  const slideAnim = direction >= 0 ? 'slide-in-right' : 'slide-in-left'

  return (
    <div className="cook-overlay" role="dialog" aria-modal="true">
      <div className="cook-header">
        <div className="cook-head-info">
          <span className="cook-title">{meal.title}</span>
          <span className="cook-step-count">
            {isMise
              ? 'Get ready'
              : isFinish
                ? 'All done'
                : `Step ${stepIdx + 1} of ${steps.length}`}
          </span>
        </div>
        <button className="cook-close" onClick={onClose} aria-label="Close cook mode">
          <X size={20} strokeWidth={2.4} />
        </button>
      </div>
      <div className="cook-progress">
        <div className="cook-progress-fill" style={{ width: `${progressPct}%` }} />
      </div>

      {otherTimers.length > 0 && (
        <div className="cook-timer-bar">
          {otherTimers.map(({ id, t, jump }) => (
            <TimerChip
              key={id}
              timer={t}
              onToggle={() => (t.running ? pause(id) : start(id, t.seconds, t.label))}
              onDismiss={() => dismiss(id)}
              onJump={() => {
                setDirection(jump > index ? 1 : -1)
                setIndex(jump)
              }}
            />
          ))}
        </div>
      )}

      <div
        className="cook-slide-area"
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
      >
        <div className="cook-slide" key={index} style={{ animationName: slideAnim }}>
          {isMise ? (
            <div className="cook-mise">
              <div className="cook-icon-badge"><ChefHat size={30} strokeWidth={2} /></div>
              <h2>Mise en place</h2>
              <p className="cook-sub">Gather everything before you start — tap each as you go.</p>
              {ingredients.length > 0 ? (
                <div className="cook-ingredients">
                  {ingredients.map((ing, i) => {
                    const on = checked.has(i)
                    return (
                      <button
                        key={i}
                        className={`chip ${ing.in_stock ? 'have' : 'missing'}${on ? ' checked' : ''}`}
                        onClick={() => toggleChecked(i)}
                      >
                        {on ? '✓' : ing.in_stock ? '✓' : '+'} {ing.name}
                        {ing.quantity != null ? ` (${ing.quantity} ${ing.unit})` : ''}
                      </button>
                    )
                  })}
                </div>
              ) : (
                <p className="cook-sub">No ingredient list for this recipe.</p>
              )}
            </div>
          ) : isFinish ? (
            <div className="cook-finish">
              {confetti.length > 0 && (
                <div className="confetti" aria-hidden="true">
                  {confetti.map((c) => (
                    <i
                      key={c.id}
                      className="confetti-piece"
                      style={{
                        left: `${c.left}%`,
                        background: c.color,
                        animationDelay: `${c.delay}s`,
                        animationDuration: `${c.duration}s`,
                        transform: `rotate(${c.rotate}deg)`,
                      }}
                    />
                  ))}
                </div>
              )}
              <div className="cook-icon-badge pop"><PartyPopper size={30} strokeWidth={2} /></div>
              <h2>{cooked ? 'Cooked!' : 'Nice work!'}</h2>
              <p className="cook-sub">
                {cooked
                  ? 'Logged to your history. Enjoy your meal.'
                  : `You finished ${meal.title}.`}
              </p>

              {cooked ? (
                <button className="btn primary cook-cta" onClick={onClose}>
                  Done
                </button>
              ) : (
                <>
                  <label className="cook-decrement">
                    <input
                      type="checkbox"
                      checked={decrement}
                      onChange={(e) => setDecrement(e.target.checked)}
                    />
                    Subtract used ingredients from inventory
                  </label>
                  <button
                    className="btn primary cook-cta"
                    onClick={markCooked}
                    disabled={busy}
                  >
                    <Check size={16} strokeWidth={2.4} /> {busy ? 'Saving…' : 'Mark as cooked'}
                  </button>
                  {error && <div className="banner error">{error}</div>}
                </>
              )}
            </div>
          ) : (
            <div className="cook-step">
              <span className="cook-step-num">{stepIdx + 1}</span>
              <p className="cook-step-text">{stepText}</p>
              {durs.length > 0 && (
                <div className="cook-timers">
                  {durs.map((d, di) =>
                    d.seconds <= MAX_TIMER_SECONDS ? (
                      <TimerRing
                        key={di}
                        id={tid(stepIdx, di)}
                        seconds={d.seconds}
                        label={d.label}
                        timer={timers[tid(stepIdx, di)]}
                        onStart={() => start(tid(stepIdx, di), d.seconds, d.label)}
                        onPause={() => pause(tid(stepIdx, di))}
                        onReset={() => reset(tid(stepIdx, di), d.seconds)}
                      />
                    ) : (
                      <span key={di} className="cook-long-chip">
                        <Clock size={15} strokeWidth={2.2} /> ~{d.label}
                      </span>
                    ),
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="cook-footer">
        <button className="btn ghost" onClick={() => go(-1)} disabled={index === 0}>
          <ChevronLeft size={16} strokeWidth={2.4} /> Back
        </button>
        {!isFinish && (
          <button className="btn primary" onClick={() => go(1)}>
            {index === finishIndex - 1 ? 'Finish' : 'Next'}{' '}
            <ChevronRight size={16} strokeWidth={2.4} />
          </button>
        )}
      </div>
    </div>
  )
}
