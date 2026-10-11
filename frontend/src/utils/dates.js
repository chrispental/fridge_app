// Helpers for expires_at, which is a plain YYYY-MM-DD date (no time, no zone).
// Never feed it to new Date('YYYY-MM-DD') — that parses as UTC midnight and is
// off by one in western timezones. Split into local date parts instead.

export function daysUntil(dateStr, today = new Date()) {
  if (!dateStr) return null
  const [y, m, d] = dateStr.slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return null
  const target = new Date(y, m - 1, d)
  const base = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  return Math.round((target - base) / 86_400_000)
}

// Info for items expiring within `within` days (default 3), else null.
export function expiryInfo(dateStr, { within = 3, today = new Date() } = {}) {
  const days = daysUntil(dateStr, today)
  if (days == null || days > within) return null
  if (days < 0) return { days, expired: true, label: 'expired' }
  if (days === 0) return { days, expired: false, label: 'today' }
  if (days === 1) return { days, expired: false, label: 'tomorrow' }
  return { days, expired: false, label: `${days} days` }
}

// Format a YYYY-MM-DD string for display without timezone drift.
export function fmtDay(dateStr) {
  const [y, m, d] = (dateStr || '').slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return ''
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}

// Today's local date as YYYY-MM-DD, plus an offset in days (for quick-pick chips).
export function localDatePlus(days = 0) {
  const t = new Date()
  t.setDate(t.getDate() + days)
  const pad = (n) => String(n).padStart(2, '0')
  return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}`
}

// Add whole days to a YYYY-MM-DD string, staying in local-date space.
export function addDays(dateStr, days) {
  const [y, m, d] = (dateStr || '').slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return null
  const t = new Date(y, m - 1, d + days)
  const pad = (n) => String(n).padStart(2, '0')
  return `${t.getFullYear()}-${pad(t.getMonth() + 1)}-${pad(t.getDate())}`
}

// "Sat, Oct 11" for a YYYY-MM-DD string; '' when the string is not a date.
export function fmtWeekday(dateStr) {
  const [y, m, d] = (dateStr || '').slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return ''
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric',
  })
}

// "Day 3 · Mon, Oct 13" when the plan has a start date, else just "Day 3".
export function planSlotLabel(startDate, slotIndex) {
  const day = `Day ${slotIndex + 1}`
  const date = startDate ? fmtWeekday(addDays(startDate, slotIndex)) : ''
  return date ? `${day} · ${date}` : day
}
