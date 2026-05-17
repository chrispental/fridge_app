import { useState } from 'react'
import { Link } from 'react-router-dom'
import MealCard from '../components/MealCard.jsx'
import { api } from '../api/client.js'

export default function SuggestMeal() {
  const [meals, setMeals] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function suggest() {
    setBusy(true)
    setError(null)
    setMeals(null)
    try {
      setMeals(await api.suggestMeals(3))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h1>What should I eat?</h1>
      <p>Meal ideas based on what's in your fridge and your preferences.</p>

      <button className="btn primary big" onClick={suggest} disabled={busy}>
        {busy ? 'Thinking…' : '🍳 Suggest a meal'}
      </button>

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

      {meals && meals.map((m) => <MealCard key={m.id} meal={m} />)}
    </div>
  )
}
