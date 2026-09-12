import { useSyncExternalStore } from 'react'

const KEY = 'fridge-chef-theme'
const choices = ['light', 'dark', 'system']
const media = window.matchMedia('(prefers-color-scheme: dark)')
let preference = 'light'
try {
  const saved = localStorage.getItem(KEY)
  if (choices.includes(saved)) preference = saved
} catch { /* Appearance still works when browser storage is unavailable. */ }
const listeners = new Set()

function apply() {
  const resolved = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference
  document.documentElement.dataset.theme = resolved
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', resolved === 'dark' ? '#17191c' : '#f7f8f2')
  listeners.forEach((listener) => listener())
}

export function setTheme(value) {
  if (!choices.includes(value)) return
  preference = value
  try { localStorage.setItem(KEY, value) } catch { /* Keep the in-memory choice. */ }
  apply()
}

media.addEventListener('change', () => { if (preference === 'system') apply() })
window.addEventListener('storage', (event) => {
  if (event.key !== KEY && event.key !== null) return
  preference = choices.includes(event.newValue) ? event.newValue : 'light'
  apply()
})
apply()

function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function useTheme() {
  return useSyncExternalStore(subscribe, () => preference)
}
