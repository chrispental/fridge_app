import { useState } from 'react'
import {
  Clock, Star, Users, Check, Truck, RefreshCw, ChevronDown, ChevronUp,
  ThumbsUp, ThumbsDown, ExternalLink, Play, ShoppingCart,
} from 'lucide-react'
import {
  useCookMeal, useSubmitFeedback, useOrderDelivery, useImportMealToList,
} from '../api/queries.js'
import { toast } from './Toast.jsx'
import CookMode from './CookMode.jsx'

const FEEDBACK_TAGS = [
  'Too salty', 'Too bland', 'Too spicy', 'Too sweet',
  'Too dry', 'Too greasy', 'Too slow', 'Loved it',
]

export default function MealCard({
  meal,
  onSwap = null,
  deliveryAvailable = false,
  nextDeliveryDate = null,
}) {
  const recipe = meal.recipe_json || {}
  const [expanded, setExpanded] = useState(false)
  const [cooking, setCooking] = useState(false)
  const [decrement, setDecrement] = useState(true)
  const [swapBusy, setSwapBusy] = useState(false)

  const cookMutation = useCookMeal()
  const feedbackMutation = useSubmitFeedback()
  const orderMutation = useOrderDelivery()
  const importMutation = useImportMealToList()

  // Status is derived from the cached meal (kept fresh by optimistic updates) or,
  // for meals rendered from a static mutation result, from this card's mutations.
  const cooked = meal.status === 'cooked' || cookMutation.isSuccess
  const ordered = meal.status === 'ordered' || orderMutation.isSuccess
  const deliveryOptions =
    orderMutation.data?.recipe_json?.delivery_options ||
    recipe.delivery_options ||
    []

  // Post-cook feedback form state (also editable later from History).
  const [rating, setRating] = useState(meal.rating ?? null)
  const [tags, setTags] = useState(meal.feedback_tags || [])
  const [notes, setNotes] = useState(meal.feedback_notes || '')
  const [fbSaved, setFbSaved] = useState(false)

  function setRatingDirty(v) {
    setRating((cur) => (cur === v ? null : v))
    setFbSaved(false)
  }
  function toggleTag(tag) {
    setTags((cur) => (cur.includes(tag) ? cur.filter((t) => t !== tag) : [...cur, tag]))
    setFbSaved(false)
  }
  function saveFeedback() {
    feedbackMutation.mutate(
      { id: meal.id, rating, tags, notes: notes.trim() || null },
      {
        onSuccess: () => {
          setFbSaved(true)
          toast.success('Feedback saved')
        },
      },
    )
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

  const ingredients = recipe.ingredients || []
  const steps = recipe.steps || []
  const missing = recipe.missing_ingredients || []
  const outOfStock = ingredients.some((i) => !i.in_stock) || missing.length > 0
  const hasPhoto = Boolean(recipe.image_url)

  function addMissingToList() {
    importMutation.mutate(meal.id, {
      onSuccess: (items) =>
        toast.success(
          items.length > 0
            ? `Added ${items.length} item${items.length === 1 ? '' : 's'} to your shopping list`
            : 'Everything is already on your list',
        ),
    })
  }

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

        {outOfStock && !ordered && (
          <button
            className="link-btn"
            onClick={addMissingToList}
            disabled={importMutation.isPending}
          >
            <ShoppingCart size={14} strokeWidth={2.2} style={{ verticalAlign: '-2px' }} />{' '}
            {importMutation.isPending ? 'Adding…' : 'Add missing to shopping list'}
          </button>
        )}

        {recipe.source?.url && (
          <p className="recipe-source">
            <a href={recipe.source.url} target="_blank" rel="noreferrer">
              View full recipe <ExternalLink size={13} strokeWidth={2.2} style={{ verticalAlign: '-2px' }} />
            </a>
          </p>
        )}

        {expanded ? (
          <>
            {steps.length > 0 ? (
              <ol className="steps">
                {steps.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ol>
            ) : (
              <p>No instructions provided.</p>
            )}
            <button className="link-btn" onClick={() => setExpanded(false)}>
              Hide instructions <ChevronUp size={15} strokeWidth={2.2} style={{ verticalAlign: '-3px' }} />
            </button>
          </>
        ) : (
          <button className="link-btn" onClick={() => setExpanded(true)}>
            Show instructions <ChevronDown size={15} strokeWidth={2.2} style={{ verticalAlign: '-3px' }} />
          </button>
        )}

        {steps.length > 0 && (
          <button className="btn primary begin-cooking" onClick={() => setCooking(true)}>
            <Play size={15} strokeWidth={2.4} /> {cooked ? 'Cook again' : 'Begin cooking'}
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

            <button
              className="btn"
              onClick={saveFeedback}
              disabled={feedbackMutation.isPending || fbSaved}
            >
              {feedbackMutation.isPending ? 'Saving…' : fbSaved ? 'Saved ✓' : 'Save feedback'}
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
                onClick={() => orderMutation.mutate(meal.id)}
                disabled={orderMutation.isPending || !deliveryAvailable}
                title={
                  deliveryAvailable
                    ? 'Order this meal for delivery'
                    : nextDeliveryDate
                      ? `Weekly delivery used — next available ${nextDeliveryDate}`
                      : 'Set your location in Settings to order delivery'
                }
              >
                <Truck size={15} strokeWidth={2.2} /> {orderMutation.isPending ? 'Ordering…' : 'Order delivery'}
              </button>
              <button
                className="btn"
                onClick={() => cookMutation.mutate({ id: meal.id, decrement })}
                disabled={cookMutation.isPending}
              >
                <Check size={15} strokeWidth={2.4} /> {cookMutation.isPending ? 'Saving…' : 'I cooked this'}
              </button>
            </div>
          </div>
        )}

        {orderMutation.error && (
          <div className="banner error">{orderMutation.error.message}</div>
        )}
      </div>

      {cooking && (
        <CookMode
          meal={meal}
          onClose={() => setCooking(false)}
          onCook={(dec) => cookMutation.mutateAsync({ id: meal.id, decrement: dec })}
        />
      )}
    </div>
  )
}
