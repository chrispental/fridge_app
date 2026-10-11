// Store sections for the shopping list, in walking order. The values are the
// inventory category vocabulary and must stay in sync with AISLES in
// backend/app/services/aisles.py (the backend guesses a row's section).
export const AISLES = [
  { value: 'produce', label: 'Produce', emoji: '🥕' },
  { value: 'bakery', label: 'Bakery', emoji: '🍞' },
  { value: 'meat', label: 'Meat', emoji: '🥩' },
  { value: 'seafood', label: 'Seafood', emoji: '🐟' },
  { value: 'dairy', label: 'Dairy & eggs', emoji: '🧀' },
  { value: 'frozen', label: 'Frozen', emoji: '❄️' },
  { value: 'pantry', label: 'Pantry', emoji: '🥫' },
  { value: 'condiment', label: 'Condiments', emoji: '🫙' },
  { value: 'beverage', label: 'Drinks', emoji: '🧃' },
  { value: 'other', label: 'Other', emoji: '🛒' },
]

// Group rows by aisle, keeping AISLES order and dropping empty sections.
export function groupByAisle(rows) {
  return AISLES.map((a) => ({
    ...a,
    items: rows.filter((r) => (r.category || 'other') === a.value),
  })).filter((a) => a.items.length > 0)
}
