// Shelf-life prefill for manual entry — kept in sync with the backend table in
// backend/app/services/expiry.py (photo scans get the same estimate server-side).
// It is a suggestion the user sees and can change before saving, never a fact.
import { localDatePlus } from './dates.js'

const CATEGORY_DAYS = {
  produce: 7, vegetable: 7, fruit: 7, herb: 5,
  dairy: 10, cheese: 14, egg: 21,
  meat: 3, poultry: 3, seafood: 2, fish: 2, deli: 5,
  bakery: 4, bread: 4, leftover: 4, frozen: 90,
}
const FREEZER_DAYS = 90

// Categories offered as suggestions in the item form (free text still allowed).
export const CATEGORIES = [
  'produce', 'dairy', 'meat', 'seafood', 'pantry', 'frozen',
  'beverage', 'condiment', 'bakery', 'leftover', 'other',
]

// YYYY-MM-DD estimate from category + storage, or null when there is no basis for one.
export function estimateExpiry(category, storage) {
  if ((storage || '').toLowerCase() === 'freezer') return localDatePlus(FREEZER_DAYS)
  const cat = (category || '').toLowerCase()
  for (const [keyword, days] of Object.entries(CATEGORY_DAYS)) {
    if (cat.includes(keyword)) return localDatePlus(days)
  }
  return null
}
