import { useEffect, useState } from 'react'
import MealCard from '../components/MealCard.jsx'
import { api } from '../api/client.js'

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'cooked', label: 'Cooked' },
  { value: 'suggested', label: 'Suggested' },
]

const fmtDate = (iso) => (iso ? new Date(iso + 'Z').toLocaleDateString() : null)

export default function HistoryPage() {
  const [meals, setMeals] = useState(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState(null)
  const [delivery, setDelivery] = useState(null)

  function load() {
    api
      .getMeals(filter || undefined)
      .then(setMeals)
      .catch((e) => setError(e.message))
  }
  useEffect(load, [filter])

  function loadDelivery() {
    api.getDeliveryStatus().then(setDelivery).catch(() => setDelivery(null))
  }
  useEffect(loadDelivery, [])

  const deliveryAvailable = delivery ? !delivery.used : true
  const nextDeliveryDate = fmtDate(delivery?.next_available_at)

  function onChanged() {
    load()
    loadDelivery()
  }

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
          <MealCard
            meal={m}
            onChanged={onChanged}
            deliveryAvailable={deliveryAvailable}
            nextDeliveryDate={nextDeliveryDate}
          />
          <div className="ts">
            {m.status === 'ordered' && m.delivery_ordered_at
              ? `Ordered ${new Date(m.delivery_ordered_at + 'Z').toLocaleDateString()}`
              : m.status === 'cooked' && m.cooked_at
                ? `Cooked ${new Date(m.cooked_at + 'Z').toLocaleDateString()}`
                : `Suggested ${new Date(m.suggested_at + 'Z').toLocaleDateString()}`}
          </div>
        </div>
      ))}
    </div>
  )
}
