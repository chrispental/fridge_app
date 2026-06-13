// Heuristic duration parser for cooking steps.
//
// Recipe steps are plain prose ("Simmer the sauce for 10 minutes"). The AI already
// writes timings into the text, so we scan for the first time mention and turn it into
// a countdown. A miss is harmless — the step just shows no timer.

// Don't run an in-app countdown for very long waits (marinate overnight, etc.).
export const MAX_TIMER_SECONDS = 2 * 3600

const UNIT_SECONDS = {
  hour: 3600,
  minute: 60,
  second: 1,
}

// Map every accepted spelling to a canonical unit key.
function unitKey(raw) {
  const u = raw.toLowerCase()
  if (u.startsWith('h')) return 'hour'
  if (u.startsWith('m')) return 'minute'
  if (u.startsWith('s')) return 'second'
  return null
}

// Number, optional range upper-bound, then a time unit. Anchored on word boundaries so
// "350°F" / "2 cups" / "Step 1" don't match (those aren't time units).
const DURATION_RE =
  /\b(\d+(?:\.\d+)?)(?:\s*[–—-]\s*(\d+(?:\.\d+)?))?\s*(hours?|hrs?|minutes?|mins?|min|seconds?|secs?|sec)\b/i

function humanLabel(seconds) {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.round(seconds % 60)
  const parts = []
  if (h) parts.push(`${h} hr`)
  if (m) parts.push(`${m} min`)
  if (s && !h) parts.push(`${s} sec`)
  return parts.join(' ') || '0 sec'
}

/**
 * Parse every time duration out of a cooking step, in order of appearance.
 * Handles ranges (uses the upper bound) and "per side"/"each side" (doubles, since
 * the stated time is for one side only).
 * @param {string} text
 * @returns {Array<{ seconds: number, label: string, perSide: boolean }>}
 */
export function parseStepDurations(text) {
  if (!text || typeof text !== 'string') return []
  const re = new RegExp(DURATION_RE.source, 'gi')
  const out = []
  let m
  while ((m = re.exec(text))) {
    const key = unitKey(m[3])
    if (!key) continue
    // For a range ("10–15 minutes") use the upper bound — better the timer runs a touch
    // long than alert early.
    const upper = m[2] != null ? parseFloat(m[2]) : parseFloat(m[1])
    if (!Number.isFinite(upper) || upper <= 0) continue
    let seconds = Math.round(upper * UNIT_SECONDS[key])

    // "...3 minutes per side" / "each side" means the time is per side — double it.
    const after = text.slice(re.lastIndex, re.lastIndex + 14).toLowerCase()
    const perSide = /^[\s,]*(per|each|a|on each)\s+side/.test(after)
    if (perSide) seconds *= 2

    out.push({ seconds, label: humanLabel(seconds) + (perSide ? ' total' : ''), perSide })
  }
  return out
}

/**
 * Parse the first time duration out of a cooking step.
 * @param {string} text
 * @returns {{ seconds: number, label: string } | null}
 */
export function parseStepDuration(text) {
  return parseStepDurations(text)[0] || null
}
