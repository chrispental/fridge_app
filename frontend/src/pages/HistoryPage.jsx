import { useEffect, useState } from 'react'
import MealCard from '../components/MealCard.jsx'
import { api } from '../api/client.js'

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'cooked', label: 'Cooked' },
  { value: 'suggested', label: 'Suggested' },
]

export default function HistoryPage() {
  const [meals, setMeals] = useState(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState(null)

  function load() {
    api
      .getMeals(filter || undefined)
      .then(setMeals)
      .catch((e) => setError(e.message))
  }
  useEffect(load, [filter])

  if (error) return <div className="banner error">{error}</div>
  if (!meals) return <div className="loading">Loading…</div>

  return (
    <div>
      <h1>Meal history</h1>
      <p>Every suggestion is logged here — that's how meals avoid repeating.</p>

      <div className="filters">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            className={filter === f.value ? 'active' : ''}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>

      {meals.length === 0 && <p className="empty">No meals yet.</p>}

      {meals.map((m) => (
        <div key={m.id}>
          <MealCard meal={m} onChanged={load} />
          <div className="ts">
            {m.status === 'cooked' && m.cooked_at
              ? `Cooked ${new Date(m.cooked_at + 'Z').toLocaleDateString()}`
              : `Suggested ${new Date(m.suggested_at + 'Z').toLocaleDateString()}`}
          </div>
        </div>
      ))}
    </div>
  )
}
