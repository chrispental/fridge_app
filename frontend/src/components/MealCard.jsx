import { useState } from 'react'
import { api } from '../api/client.js'

export default function MealCard({
  meal,
  onChanged,
  onSwap = null,
  deliveryAvailable = false,
  nextDeliveryDate = null,
}) {
  const recipe = meal.recipe_json || {}
  const [expanded, setExpanded] = useState(false)
  const [decrement, setDecrement] = useState(true)
  const [busy, setBusy] = useState(false)
  const [swapBusy, setSwapBusy] = useState(false)

  async function handleSwap() {
    if (!onSwap) return
    setSwapBusy(true)
    try {
      await onSwap()
    } finally {
      setSwapBusy(false)
    }
  }
  const [cooked, setCooked] = useState(meal.status === 'cooked')
  const [ordered, setOrdered] = useState(meal.status === 'ordered')
  const [deliveryOptions, setDeliveryOptions] = useState(recipe.delivery_options || [])
  const [orderBusy, setOrderBusy] = useState(false)
  const [orderError, setOrderError] = useState(null)

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

  async function orderDelivery() {
    setOrderBusy(true)
    setOrderError(null)
    try {
      const updated = await api.orderDelivery(meal.id)
      setOrdered(true)
      setDeliveryOptions(updated.recipe_json?.delivery_options || [])
      onChanged?.()
    } catch (e) {
      setOrderError(e.message)
    } finally {
      setOrderBusy(false)
    }
  }

  const ingredients = recipe.ingredients || []
  const steps = recipe.steps || []
  const missing = recipe.missing_ingredients || []

  return (
    <div className="meal-card">
      {recipe.image_url && (
        <img className="recipe-image" src={recipe.image_url} alt={meal.title} />
      )}

      <div className="meal-head" onClick={() => setExpanded((v) => !v)}>
        <h3>{meal.title}</h3>
        <div className="meal-meta">
          {recipe.cuisine && <span>{recipe.cuisine}</span>}
          {recipe.cooking_method && <span className="method-chip">{recipe.cooking_method}</span>}
          {recipe.estimated_time_minutes && <span>⏱ {recipe.estimated_time_minutes} min</span>}
          {recipe.complexity && <span>★ {recipe.complexity}/5</span>}
          {recipe.servings && <span>🍽 serves {recipe.servings}</span>}
        </div>
      </div>

      {onSwap && (
        <div className="swap-row">
          <button className="btn ghost" onClick={handleSwap} disabled={swapBusy}>
            {swapBusy ? 'Swapping…' : '🔄 Swap this day'}
          </button>
        </div>
      )}

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

      {recipe.source?.url && (
        <p className="recipe-source">
          <a href={recipe.source.url} target="_blank" rel="noreferrer">
            View full recipe ↗
          </a>
        </p>
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

      {ordered ? (
        <div className="delivery-block">
          <div className="cooked-badge">🚚 Ordered for delivery</div>
          {deliveryOptions.length > 0 && (
            <ul className="delivery-links">
              {deliveryOptions.map((o, i) => (
                <li key={i}>
                  <a href={o.url} target="_blank" rel="noreferrer">
                    {o.title || o.url} ↗
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : cooked ? (
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
          <div className="cook-actions">
            <button
              className="btn"
              onClick={orderDelivery}
              disabled={orderBusy || !deliveryAvailable}
              title={
                deliveryAvailable
                  ? 'Order this meal for delivery'
                  : nextDeliveryDate
                    ? `Weekly delivery used — next available ${nextDeliveryDate}`
                    : 'Set your location in Settings to order delivery'
              }
            >
              {orderBusy ? 'Ordering…' : '🚚 Order delivery'}
            </button>
            <button className="primary" onClick={cook} disabled={busy}>
              {busy ? 'Saving…' : 'I cooked this'}
            </button>
          </div>
        </div>
      )}

      {orderError && <div className="banner error">{orderError}</div>}
    </div>
  )
}
