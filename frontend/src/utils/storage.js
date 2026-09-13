export function readStored(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw == null ? fallback : JSON.parse(raw)
  } catch {
    return fallback
  }
}

export function writeStored(key, value) {
  try {
    if (value == null) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(value))
  } catch { /* Private browsing and full storage must not prevent cooking. */ }
}

export const kitchenKey = (userId, kind, id) => `fridge:${userId || 'local'}:${kind}:${id}`
