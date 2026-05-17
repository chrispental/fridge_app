// Thin fetch wrapper around the backend API. All calls are same-origin (/api).
const BASE = '/api'

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(BASE + path, options)
  } catch {
    throw new Error('Could not reach the server. Is the backend running?')
  }
  if (res.status === 204) return null

  const text = await res.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = null
    }
  }

  if (!res.ok) {
    const detail = data && data.detail
    const message =
      typeof detail === 'string'
        ? detail
        : detail
          ? JSON.stringify(detail)
          : res.statusText || 'Request failed'
    throw new Error(message)
  }
  return data
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

// US customary units — kept in sync with backend app/services/units.py
export const UNITS = [
  'tsp', 'tbsp', 'fl oz', 'cup', 'pint', 'quart', 'gallon',
  'oz', 'lb', 'piece', 'dozen', 'pack', 'can', 'jar', 'bottle', 'bunch', 'unknown',
]

export const api = {
  // Preferences
  getPreferences: () => request('/preferences'),
  getOnboardStatus: () => request('/preferences/status'),
  updatePreferences: (body) => request('/preferences', json('PUT', body)),

  // Inventory
  getInventory: () => request('/inventory'),
  addItem: (body) => request('/inventory', json('POST', body)),
  updateItem: (id, body) => request(`/inventory/${id}`, json('PATCH', body)),
  deleteItem: (id) => request(`/inventory/${id}`, { method: 'DELETE' }),

  // Photo extraction
  extractPhoto: (formData) =>
    request('/inventory/extract', { method: 'POST', body: formData }),
  getExtraction: (batchId) => request(`/inventory/extract/${batchId}`),
  confirmExtraction: (batchId, items) =>
    request(`/inventory/extract/${batchId}/confirm`, json('POST', { items })),

  // Meals
  suggestMeals: (count = 3) =>
    request(`/meals/suggest?count=${count}`, { method: 'POST' }),
  getMeals: (status) =>
    request(`/meals${status ? `?status=${status}` : ''}`),
  cookMeal: (id, decrementInventory) =>
    request(`/meals/${id}/cook`, json('POST', { decrement_inventory: decrementInventory })),
  deleteMeal: (id) => request(`/meals/${id}`, { method: 'DELETE' }),
}
