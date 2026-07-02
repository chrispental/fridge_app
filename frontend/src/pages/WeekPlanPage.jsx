import { useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarDays, RefreshCw, AlertCircle, ShoppingCart } from 'lucide-react'
import MealCard from '../components/MealCard.jsx'
import {
  useCreatePlan, useCurrentPlan, useDeletePlan, useDeliveryStatus,
  useImportPlanToList, usePlanShoppingList, useSwapPlanSlot,
} from '../api/queries.js'
import { toast } from '../components/Toast.jsx'
import { PageHeader, HeroPanel, Bento, BentoItem, PageSkeleton } from '../components/ui.jsx'

const fmtDate = (iso) => (iso ? new Date(iso + 'Z').toLocaleDateString() : null)

function ShoppingList({ data, onAddAll, adding }) {
  if (!data) return null
  const { to_buy = [], have = [], staples_assumed = [] } = data
  const line = (it) =>
    it.quantity != null ? `${it.name} (${it.quantity} ${it.unit})` : it.name

  return (
    <div className="shopping-card">
      <h2>🛒 Shopping list</h2>

      {staples_assumed.length > 0 && (
        <div className="banner info">
          🧂 Assuming you always have: {staples_assumed.join(', ')}.{' '}
          <Link to="/preferences">Edit staples</Link>
        </div>
      )}

      <div className="shopping-group">
        <h3>Need to buy ({to_buy.length})</h3>
        {to_buy.length === 0 ? (
          <p className="hint">You already have everything for this plan. 🎉</p>
        ) : (
          <>
            <div className="ingredients">
              {to_buy.map((it, i) => (
                <span key={i} className="chip missing">+ {line(it)}</span>
              ))}
            </div>
            <button
              className="btn"
              style={{ marginTop: 12 }}
              onClick={onAddAll}
              disabled={adding}
            >
              <ShoppingCart size={15} strokeWidth={2.2} />
              {adding ? 'Adding…' : 'Add all to shopping list'}
            </button>
          </>
        )}
      </div>

      {have.length > 0 && (
        <div className="shopping-group">
          <h3>Already in your fridge ({have.length})</h3>
          <div className="ingredients">
            {have.map((it, i) => (
              <span key={i} className="chip have">✓ {line(it)}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function WeekPlanPage() {
  const [count, setCount] = useState(7)

  const planQ = useCurrentPlan()
  const plan = planQ.data
  const shoppingQ = usePlanShoppingList(plan?.id)
  const deliveryQ = useDeliveryStatus()
  const createMutation = useCreatePlan()
  const deleteMutation = useDeletePlan()
  const swapMutation = useSwapPlanSlot()
  const importMutation = useImportPlanToList()

  const busy = createMutation.isPending || deleteMutation.isPending
  const error = createMutation.error?.message || deleteMutation.error?.message

  // Returned promise lets MealCard show its own "Swapping…" state.
  const swap = (slot) => swapMutation.mutateAsync({ planId: plan.id, slot })

  function addAllToList() {
    importMutation.mutate(plan.id, {
      onSuccess: (items) =>
        toast.success(
          items.length > 0
            ? `Added ${items.length} item${items.length === 1 ? '' : 's'} to your shopping list`
            : 'Everything is already on your list',
        ),
    })
  }

  if (planQ.isPending) return <PageSkeleton />

  const delivery = deliveryQ.data
  const deliveryAvailable = delivery ? !delivery.used : true
  const nextDeliveryDate = fmtDate(delivery?.next_available_at)

  // ---- No plan yet: the create form ----
  if (!plan) {
    return (
      <HeroPanel compact>
        <div className="home-hero-greeting">
          <span className="eyebrow rule">Weekly plan</span>
          <h1>Plan your week</h1>
        </div>
        <p>
          Generate a few days of meals at once, then see exactly what you already
          have and what you'll need to buy.
        </p>

        <div className="plan-toolbar">
          <div className="field">
            <label>How many meals?</label>
            <input
              type="number"
              min="1"
              max="14"
              value={count}
              onChange={(e) => setCount(e.target.value)}
            />
          </div>
          <button
            className="btn primary big"
            onClick={() => createMutation.mutate(Number(count) || 7)}
            disabled={busy}
          >
            <CalendarDays size={18} strokeWidth={2.2} />
            {busy ? 'Planning…' : 'Plan my week'}
          </button>
        </div>

        {busy && (
          <p className="hint">
            Building your week — generating each meal takes a few seconds.
          </p>
        )}

        {error && (
          <div className="banner error">
            <AlertCircle size={16} strokeWidth={2.2} style={{ verticalAlign: '-3px' }} /> {error}
            <div style={{ marginTop: '0.5rem' }}>
              <Link to="/inventory">Check your inventory</Link> ·{' '}
              <Link to="/preferences">adjust preferences</Link>
            </div>
          </div>
        )}
      </HeroPanel>
    )
  }

  // ---- Existing plan ----
  return (
    <div className="wide">
      <PageHeader
        eyebrow="Weekly plan"
        title="Your week"
        subtitle={`${plan.entries.length} meal${plan.entries.length === 1 ? '' : 's'} planned`}
      >
        <button
          className="btn ghost"
          onClick={() => deleteMutation.mutate(plan.id)}
          disabled={busy}
        >
          <RefreshCw size={16} strokeWidth={2.2} />
          {busy ? 'Working…' : 'Start a new plan'}
        </button>
      </PageHeader>

      {error && (
        <div className="banner error">
          <AlertCircle size={16} strokeWidth={2.2} style={{ verticalAlign: '-3px' }} /> {error}
        </div>
      )}

      <Bento>
        {/* LEFT: the week's meals, with per-day swap */}
        <BentoItem span={8}>
          <div className="stack">
            {plan.entries.map((entry) => (
              <MealCard
                key={entry.meal.id}
                meal={entry.meal}
                onSwap={() => swap(entry.slot_index)}
                deliveryAvailable={deliveryAvailable}
                nextDeliveryDate={nextDeliveryDate}
              />
            ))}
          </div>
        </BentoItem>

        {/* RIGHT: sticky shopping-list rail */}
        <BentoItem span={4}>
          <div style={{ position: 'sticky', top: 24 }}>
            <ShoppingList
              data={shoppingQ.data}
              onAddAll={addAllToList}
              adding={importMutation.isPending}
            />
          </div>
        </BentoItem>
      </Bento>
    </div>
  )
}
