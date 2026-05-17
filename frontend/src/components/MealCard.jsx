import { useState } from 'react'
import { api } from '../api/client.js'

export default function MealCard({ meal, onChanged }) {
  const recipe = meal.recipe_json || {}
  const [expanded, setExpanded] = useState(false)
  const [decrement, setDecrement] = useState(true)
  const [busy, setBusy] = useState(false)
  const [cooked, setCooked] = useState(meal.status === 'cooked')

  async function cook() {
    setBusy(true)
    try {
      await api.cookMeal(meal.id, decrement)
      setCooked(true)
      onChanged?.()
    } catch (e) {
      alert(e.message)
    } finally {
      setBusy(false)
    }
  }

  const ingredients = recipe.ingredients || []
  const steps = recipe.steps || []
  const missing = recipe.missing_ingredients || []

  return (
    <div className="meal-card">
      <div className="meal-head" onClick={() => setExpanded((v) => !v)}>
        <h3>{meal.title}</h3>
        <div className="meal-meta">
          {recipe.cuisine && <span>{recipe.cuisine}</span>}
          {recipe.estimated_time_minutes && <span>⏱ {recipe.estimated_time_minutes} min</span>}
          {recipe.complexity && <span>★ {recipe.complexity}/5</span>}
          {recipe.servings && <span>🍽 serves {recipe.servings}</span>}
        </div>
      </div>

      {ingredients.length > 0 && (
        <div className="ingredients">
          {ingredients.map((ing, i) => (
            <span key={i} className={`chip ${ing.in_stock ? 'have' : 'missing'}`}>
              {ing.in_stock ? '✓' : '+'} {ing.name}
              {ing.quantity != null ? ` (${ing.quantity} ${ing.unit})` : ''}
            </span>
          ))}
        </div>
      )}

      {missing.length > 0 && (
        <p className="missing-note">🛒 You'll need to buy: {missing.join(', ')}</p>
      )}

      {expanded ? (
        steps.length > 0 ? (
          <ol className="steps">
            {steps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        ) : (
          <p>No instructions provided.</p>
        )
      ) : (
        <button className="link-btn" onClick={() => setExpanded(true)}>
          Show instructions ▾
        </button>
      )}

      {cooked ? (
        <div className="cooked-badge">✓ Cooked</div>
      ) : (
        <div className="cook-row">
          <label>
            <input
              type="checkbox"
              checked={decrement}
              onChange={(e) => setDecrement(e.target.checked)}
            />
            Subtract used ingredients from inventory
          </label>
          <button className="primary" onClick={cook} disabled={busy}>
            {busy ? 'Saving…' : 'I cooked this'}
          </button>
        </div>
      )}
    </div>
  )
}
