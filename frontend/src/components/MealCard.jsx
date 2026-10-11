import { useRef, useState } from 'react'
import {
  Clock, Star, Users, Check, Truck, RefreshCw, ChevronDown, ChevronUp,
  ThumbsUp, ThumbsDown, ExternalLink, Play, ShoppingCart, Wand2,
} from 'lucide-react'
import {
  useCookMeal, useSubmitFeedback, useOrderDelivery, useImportMealToList, useAdjustMeal,
} from '../api/queries.js'
import { toast } from './toast.js'
import CookMode from './CookMode.jsx'
import StepSafety from './StepSafety.jsx'
import MealIcon from './MealIcon.jsx'
import { formatAmount, formatQty } from '../utils/quantity.js'
import { useAuth } from '../auth/useAuth.js'
import { canResume, useCookProgress } from '../utils/cookingProgress.js'

const FEEDBACK_TAGS = [
  'Too salty', 'Too bland', 'Too spicy', 'Too sweet',
  'Too dry', 'Too greasy', 'Too slow', 'Loved it',
]

// One-tap rewrites; anything else goes in the free-text box.
const ADJUST_CHIPS = [
  'Vegetarian', 'Faster', 'Spicier', 'Milder', 'Only what I have', 'Fewer dishes',
]

export default function MealCard({
  meal,
  onSwap = null,
  deliveryAvailable = false,
  nextDeliveryDate = null,
}) {
  const recipe = meal.recipe_json || {}
  const { session } = useAuth()
  const savedProgress = useCookProgress(session?.user?.id, meal.id)
  const [expanded, setExpanded] = useState(false)
  const [cooking, setCooking] = useState(false)
  const [decrement, setDecrement] = useState(true)
  const [leftovers, setLeftovers] = useState(false)
  const [swapBusy, setSwapBusy] = useState(false)
  const [confirmingDelivery, setConfirmingDelivery] = useState(false)
  const [adjusting, setAdjusting] = useState(false)
  const [instruction, setInstruction] = useState('')

  const cookMutation = useCookMeal()
  const adjustMutation = useAdjustMeal()
  const cookRequestId = useRef(crypto.randomUUID())
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

  // Rewrites the recipe in place (same meal id); the cache patch re-renders this card.
  function applyAdjustment(text) {
    const value = (text ?? instruction).trim()
    if (!value || adjustMutation.isPending) return
    adjustMutation.mutate(
      { id: meal.id, instruction: value },
      {
        onSuccess: () => {
          setAdjusting(false)
          setInstruction('')
          setExpanded(true)
          toast.success('Recipe adjusted')
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
  const adjustments = recipe.adjustments || []
  const canAdjust = !cooked && !ordered
  const outOfStock = ingredients.some((i) => ['missing', 'partial'].includes(i.stock_status) || (!i.stock_status && !i.in_stock)) || missing.length > 0
  const checkAmounts = ingredients.some((i) => i.stock_status === 'check')

  function addMissingToList(again = false) {
    importMutation.mutate({ mealId: meal.id, copyId: again ? crypto.randomUUID() : undefined }, {
      onSuccess: (items) =>
        toast.success(
          items.length > 0
            ? `Added ${items.length} item${items.length === 1 ? '' : 's'} to your shopping list`
            : 'Already imported. Use Add again for another cook.',
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
        className="meal-media no-photo"
        onClick={() => setExpanded((v) => !v)}
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setExpanded((v) => !v)
          }
        }}
      >
        <div className="meal-media-body">
          <span className="meal-icon"><MealIcon method={recipe.cooking_method} /></span>
          <h3>{meal.title}</h3>
          {meta}
        </div>
      </div>

      <div className="meal-body">
        {(onSwap || canAdjust) && (
          <div className="swap-row">
            {canAdjust && (
              <button
                className="btn ghost"
                onClick={() => setAdjusting((v) => !v)}
                aria-expanded={adjusting}
                disabled={adjustMutation.isPending}
              >
                <Wand2 size={15} strokeWidth={2.2} /> {adjustMutation.isPending ? 'Adjusting…' : 'Adjust recipe'}
              </button>
            )}
            {onSwap && (
              <button className="btn ghost" onClick={handleSwap} disabled={swapBusy}>
                <RefreshCw size={15} strokeWidth={2.2} /> {swapBusy ? 'Swapping…' : 'Swap this meal'}
              </button>
            )}
          </div>
        )}

        {adjusting && canAdjust && (
          <div className="adjust-panel" role="group" aria-label="Adjust this recipe">
            <p className="hint">How should this recipe change? Your allergies and the weather still apply.</p>
            <div className="feedback-tags">
              {ADJUST_CHIPS.map((c) => (
                <button
                  key={c}
                  type="button"
                  className="chip-toggle"
                  onClick={() => applyAdjustment(c)}
                  disabled={adjustMutation.isPending}
                >
                  {c}
                </button>
              ))}
            </div>
            <form
              className="adjust-form"
              onSubmit={(e) => {
                e.preventDefault()
                applyAdjustment()
              }}
            >
              <input
                className="adjust-input"
                aria-label="Describe the change"
                placeholder="e.g. swap the chicken for tofu, halve the garlic…"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                maxLength={500}
                disabled={adjustMutation.isPending}
              />
              <button type="submit" className="btn primary" disabled={adjustMutation.isPending || !instruction.trim()}>
                {adjustMutation.isPending ? 'Adjusting…' : 'Apply'}
              </button>
              <button type="button" className="btn ghost" onClick={() => setAdjusting(false)} disabled={adjustMutation.isPending}>
                Cancel
              </button>
            </form>
            {adjustMutation.isPending && <p className="hint">Rewriting the recipe — this takes a few seconds.</p>}
            {adjustMutation.error && <div className="banner error" role="alert">{adjustMutation.error.message}</div>}
          </div>
        )}

        {adjustments.length > 0 && (
          <p className="adjusted-note">
            <Wand2 size={13} strokeWidth={2.2} style={{ verticalAlign: '-2px' }} /> Adjusted: {adjustments.join(' · ')}
          </p>
        )}

        {ingredients.length > 0 && (
          <div className="ingredients">
            {ingredients.map((ing, i) => (
              <span key={i} className={`chip ${ing.stock_status === 'check' ? 'warn' : ing.in_stock ? 'have' : 'missing'}`}>
                {ing.stock_status === 'check' ? '?' : ing.in_stock ? '✓' : '+'} {ing.name}
                {ing.quantity != null ? ` (${formatAmount(ing.quantity, ing.unit)})` : ''}
                {ing.stock_status === 'check' ? ' · check amount' : ing.stock_status === 'partial' ? ` · need ${formatQty(ing.missing_quantity)} more` : ''}
              </span>
            ))}
          </div>
        )}

        {missing.length > 0 && (
          <p className="missing-note">🛒 You'll need to buy: {missing.join(', ')}</p>
        )}

        {outOfStock && !ordered && (
          <div className="import-row">
            <button
              className="link-btn"
              onClick={() => addMissingToList()}
              disabled={importMutation.isPending}
            >
              <ShoppingCart size={14} strokeWidth={2.2} style={{ verticalAlign: '-2px' }} />{' '}
              {importMutation.isPending ? 'Adding…' : importMutation.isSuccess ? 'Already added' : 'Add missing to shopping list'}
            </button>
            {importMutation.isSuccess && <button className="link-btn" onClick={() => addMissingToList(true)} disabled={importMutation.isPending}>Add again for another cook</button>}
          </div>
        )}

        {checkAmounts && <p className="hint">Check ingredient amounts in your inventory before cooking. Unknown amounts are not automatically added to shopping.</p>}
        {recipe.source?.url && (
          <p className="recipe-source">
            <a href={recipe.source.url} target="_blank" rel="noreferrer">
              Related recipe <ExternalLink size={13} strokeWidth={2.2} style={{ verticalAlign: '-2px' }} />
            </a>
          </p>
        )}

        {expanded ? (
          <>
            {steps.length > 0 ? (
              <ol className="steps">
                {steps.map((s, i) => (
                  <li key={i}><StepSafety steps={steps} index={i} />{s}</li>
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
            <Play size={15} strokeWidth={2.4} /> {canResume(savedProgress, meal) ? 'Resume cooking' : cooked ? 'Cook again' : 'Begin cooking'}
          </button>
        )}

        {ordered ? (
          <div className="delivery-block">
            <div className="cooked-badge"><Truck size={16} strokeWidth={2.2} /> Delivery night</div>
            <p className="hint">
              {deliveryOptions.length > 0
                ? 'Nothing has been ordered yet — these search results may help you place the order yourself.'
                : 'Nothing has been ordered yet, and no delivery links were found. Order from your usual delivery app.'}
            </p>
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
        ) : confirmingDelivery ? (
          <div className="delivery-confirm" role="group" aria-label="Confirm delivery night">
            <p className="hint">
              Use this week's delivery night on this meal? You'll get links to delivery services and
              place the order yourself. This can't be undone.
            </p>
            <div className="cook-actions">
              <button
                className="btn primary"
                onClick={() => orderMutation.mutate(meal.id, { onSettled: () => setConfirmingDelivery(false) })}
                disabled={orderMutation.isPending}
              >
                <Truck size={15} strokeWidth={2.2} /> {orderMutation.isPending ? 'Finding links…' : 'Use delivery night'}
              </button>
              <button className="btn" onClick={() => setConfirmingDelivery(false)} disabled={orderMutation.isPending}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="cook-row">
            <div className="cook-options">
              <label>
                <input
                  type="checkbox"
                  checked={decrement}
                  onChange={(e) => setDecrement(e.target.checked)}
                />
                Subtract used ingredients from inventory
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={leftovers}
                  onChange={(e) => setLeftovers(e.target.checked)}
                />
                Save leftovers to my fridge
              </label>
            </div>
            <div className="cook-actions">
              <button
                className="btn"
                onClick={() => setConfirmingDelivery(true)}
                disabled={!deliveryAvailable}
                title={
                  deliveryAvailable
                    ? 'Use this week\'s delivery night on this meal'
                    : nextDeliveryDate
                      ? `Weekly delivery used — next available ${nextDeliveryDate}`
                      : 'Set your location in Settings to order delivery'
                }
              >
                <Truck size={15} strokeWidth={2.2} /> Order delivery
              </button>
              <button
                className="btn"
                onClick={() => cookMutation.mutate({ id: meal.id, decrement, leftovers, requestId: cookRequestId.current })}
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
          onCook={(dec, requestId, left) => cookMutation.mutateAsync({ id: meal.id, decrement: dec, requestId, leftovers: left })}
        />
      )}
    </div>
  )
}
