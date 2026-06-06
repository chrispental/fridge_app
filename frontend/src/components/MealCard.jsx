import { useState } from 'react'
import {
  Clock, Star, Users, Check, Truck, RefreshCw, ChevronDown,
  ThumbsUp, ThumbsDown, ExternalLink,
} from 'lucide-react'
import { api } from '../api/client.js'

const FEEDBACK_TAGS = [
  'Too salty', 'Too bland', 'Too spicy', 'Too sweet',
  'Too dry', 'Too greasy', 'Too slow', 'Loved it',
]

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

  // Post-cook feedback state (also editable later from History).
  const [rating, setRating] = useState(meal.rating ?? null)
  const [tags, setTags] = useState(meal.feedback_tags || [])
  const [notes, setNotes] = useState(meal.feedback_notes || '')
  const [fbBusy, setFbBusy] = useState(false)
  const [fbSaved, setFbSaved] = useState(false)

  function setRatingDirty(v) {
    setRating((cur) => (cur === v ? null : v))
    setFbSaved(false)
  }
  function toggleTag(tag) {
    setTags((cur) => (cur.includes(tag) ? cur.filter((t) => t !== tag) : [...cur, tag]))
    setFbSaved(false)
  }
  async function saveFeedback() {
    setFbBusy(true)
    try {
      await api.submitFeedback(meal.id, { rating, tags, notes: notes.trim() || null })
      setFbSaved(true)
      onChanged?.()
    } catch (e) {
      alert(e.message)
    } finally {
      setFbBusy(false)
    }
  }

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
  const hasPhoto = Boolean(recipe.image_url)

  const meta = (
    <div className="meal-meta">
      {recipe.cuisine && <span>{recipe.cuisine}</span>}
      {recipe.cooking_method && <span className="method-chip">{recipe.cooking_method}</span>}
      {recipe.estimated_time_minutes && (
        <span><Clock size={13} strokeWidth={2.2} /> {recipe.estimated_time_minutes} min</span>
      )}
      {recipe.complexity && <span><Star size={13} strokeWidth={2.2} /> {recipe.complexity}/5</span>}
      {recipe.servings && <span><Users size={13} strokeWidth={2.2} /> serves {recipe.servings}</span>}
    </div>
  )

  return (
    <div className="meal-card interactive">
      <div
        className={`meal-media${hasPhoto ? '' : ' no-photo'}`}
        onClick={() => setExpanded((v) => !v)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && setExpanded((v) => !v)}
      >
        {hasPhoto && <img src={recipe.image_url} alt={meal.title} />}
        <div className="meal-media-body">
          <h3>{meal.title}</h3>
          {meta}
        </div>
      </div>

      <div className="meal-body">
        {onSwap && (
          <div className="swap-row">
            <button className="btn ghost" onClick={handleSwap} disabled={swapBusy}>
              <RefreshCw size={15} strokeWidth={2.2} /> {swapBusy ? 'Swapping…' : 'Swap this day'}
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
              View full recipe <ExternalLink size={13} strokeWidth={2.2} style={{ verticalAlign: '-2px' }} />
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
            Show instructions <ChevronDown size={15} strokeWidth={2.2} style={{ verticalAlign: '-3px' }} />
          </button>
        )}

        {ordered ? (
          <div className="delivery-block">
            <div className="cooked-badge"><Truck size={16} strokeWidth={2.2} /> Ordered for delivery</div>
            {deliveryOptions.length > 0 && (
              <ul className="delivery-links">
                {deliveryOptions.map((o, i) => (
                  <li key={i}>
                    <a href={o.url} target="_blank" rel="noreferrer">
                      {o.title || o.url} <ExternalLink size={12} strokeWidth={2.2} style={{ verticalAlign: '-2px' }} />
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : cooked ? (
          <div className="feedback">
            <div className="feedback-head">
              <span className="cooked-badge"><Check size={16} strokeWidth={2.4} /> Cooked</span>
              <div className="rate">
                <span>How was it?</span>
                <button
                  className={`thumb${rating === 1 ? ' on' : ''}`}
                  onClick={() => setRatingDirty(1)}
                  aria-label="Liked it"
                >
                  <ThumbsUp size={15} strokeWidth={2.2} />
                </button>
                <button
                  className={`thumb${rating === -1 ? ' on' : ''}`}
                  onClick={() => setRatingDirty(-1)}
                  aria-label="Didn't like it"
                >
                  <ThumbsDown size={15} strokeWidth={2.2} />
                </button>
              </div>
            </div>

            <div className="feedback-tags">
              {FEEDBACK_TAGS.map((t) => (
                <button
                  key={t}
                  className={`chip-toggle${tags.includes(t) ? ' on' : ''}`}
                  onClick={() => toggleTag(t)}
                >
                  {t}
                </button>
              ))}
            </div>

            <textarea
              className="idea-input"
              rows={2}
              placeholder="Anything to remember for next time? e.g. “a bit too salty”"
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value)
                setFbSaved(false)
              }}
            />

            <button className="btn" onClick={saveFeedback} disabled={fbBusy || fbSaved}>
              {fbBusy ? 'Saving…' : fbSaved ? 'Saved ✓' : 'Save feedback'}
            </button>
          </div>
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
                <Truck size={15} strokeWidth={2.2} /> {orderBusy ? 'Ordering…' : 'Order delivery'}
              </button>
              <button className="btn primary" onClick={cook} disabled={busy}>
                <Check size={15} strokeWidth={2.4} /> {busy ? 'Saving…' : 'I cooked this'}
              </button>
            </div>
          </div>
        )}

        {orderError && <div className="banner error">{orderError}</div>}
      </div>
    </div>
  )
}
