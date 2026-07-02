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
