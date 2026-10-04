import { useSyncExternalStore } from 'react'
import { kitchenKey, readStored, writeStored } from './storage.js'

const EVENT = 'fridge-cooking-progress'
export const recipeStamp = (meal) => `${meal.title}|${meal.recipe_json?.steps?.length || 0}`
export const canResume = (progress, meal) => Boolean(progress && !progress.complete &&
  Number.isInteger(progress.index) && (!progress.meal || progress.meal === recipeStamp(meal)))

function subscribe(callback) {
  window.addEventListener(EVENT, callback)
  window.addEventListener('storage', callback)
  return () => {
    window.removeEventListener(EVENT, callback)
    window.removeEventListener('storage', callback)
  }
}

export function useCookProgress(userId, id) {
  const key = kitchenKey(userId, 'cook', id)
  const raw = useSyncExternalStore(subscribe, () => {
    try { return localStorage.getItem(key) } catch { return null }
  }, () => null)
  try { return JSON.parse(raw) } catch { return null }
}

export function saveCookProgress(userId, meal, progress) {
  writeStored(kitchenKey(userId, 'cook', meal.id), progress)
  const activeKey = kitchenKey(userId, 'cook', 'active')
  if (!progress.complete) writeStored(activeKey, { id: meal.id })
  else if (readStored(activeKey, null)?.id === meal.id) writeStored(activeKey, null)
  window.dispatchEvent(new Event(EVENT))
}

export function dismissActiveCook(userId) {
  writeStored(kitchenKey(userId, 'cook', 'active'), null)
  window.dispatchEvent(new Event(EVENT))
}
