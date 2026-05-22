import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import MealCard from '../components/MealCard.jsx'
import { api } from '../api/client.js'

const fmtDate = (iso) => (iso ? new Date(iso + 'Z').toLocaleDateString() : null)

export default function SuggestMeal() {
  const [meals, setMeals] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [delivery, setDelivery] = useState(null)

  function loadDelivery() {
    api.getDeliveryStatus().then(setDelivery).catch(() => setDelivery(null))
  }
  useEffect(loadDelivery, [])

  async function suggest() {
    setBusy(true)
    setError(null)
    setMeals(null)
    try {
      setMeals(await api.suggestMeals(5))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const deliveryAvailable = delivery ? !delivery.used : true
  const nextDeliveryDate = fmtDate(delivery?.next_available_at)

  return (
    <div>
      <h1>What should I eat?</h1>
      <p>Meal ideas based on what's in your fridge and your preferences.</p>

      <button className="btn primary big" onClick={suggest} disabled={busy}>
        {busy ? 'Thinking…' : '🍳 Suggest a meal'}
      </button>

      {delivery && (
        <p className="hint">
          {deliveryAvailable
            ? '🚚 Weekly delivery available — order one meal instead of cooking.'
            : `🚚 Weekly delivery used — next available ${nextDeliveryDate}.`}
        </p>
      )}

      {busy && (
        <p className="hint">Asking the chef — this can take 10–30 seconds.</p>
      )}

      {error && (
        <div className="banner error">
          {error}
          <div style={{ marginTop: '0.5rem' }}>
            <Link to="/inventory">Check your inventory</Link> ·{' '}
            <Link to="/preferences">adjust preferences</Link>
          </div>
        </div>
      )}

      {meals && meals.length === 0 && (
        <p className="empty">No suggestions right now — try adding more inventory.</p>
      )}

      {meals &&
        meals.map((m) => (
          <MealCard
            key={m.id}
            meal={m}
            onChanged={loadDelivery}
            deliveryAvailable={deliveryAvailable}
            nextDeliveryDate={nextDeliveryDate}
          />
        ))}
    </div>
  )
}
