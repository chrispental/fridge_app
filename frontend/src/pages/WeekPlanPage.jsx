import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarDays, RefreshCw, AlertCircle, ShoppingCart } from 'lucide-react'
import MealCard from '../components/MealCard.jsx'
import {
  useCreatePlan, useCurrentPlan, useDeletePlan, useDeliveryStatus,
  useImportPlanToList, usePlanShoppingList, useSwapPlanSlot, useResumePlan,
} from '../api/queries.js'
import QueryError from '../components/QueryError.jsx'
import { toast } from '../components/toast.js'
import { PageHeader, HeroPanel, Bento, BentoItem, PageSkeleton } from '../components/ui.jsx'

const fmtDate = (iso) => (iso ? new Date(iso + 'Z').toLocaleDateString() : null)

function ShoppingList({ data, onAddAll, adding, added, planning }) {
  if (!data) return null
  const { to_buy = [], have = [], check = [], staples_assumed = [] } = data
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
        {to_buy.length === 0 && check.length === 0 ? (
          <p className="hint">{planning ? "Your shopping list updates as meals finish." : "You already have everything for this plan. 🎉"}</p>
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
              onClick={() => onAddAll(false)}
              disabled={adding || planning || to_buy.length === 0}
            >
              <ShoppingCart size={15} strokeWidth={2.2} />
              {adding ? 'Adding…' : added ? 'Already added' : 'Add all to shopping list'}
            </button>
            {added && <button className="link-btn" onClick={() => onAddAll(true)} disabled={adding || planning}>Add again for another plan</button>}
          </>
        )}
      </div>

      {check.length > 0 && (
        <div className="shopping-group">
          <h3>Check amounts ({check.length})</h3>
          <p className="hint">These are in your inventory, but their amounts or units need checking. Update inventory before importing your list.</p>
          {check.map((it, i) => <p key={i}>{line(it)}</p>)}
          <Link to="/inventory">Update inventory</Link>
        </div>
      )}
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
  const [importedPlanId, setImportedPlanId] = useState(null)
  const requestId = useRef(crypto.randomUUID())

  const planQ = useCurrentPlan()
  const plan = planQ.data
  const shoppingQ = usePlanShoppingList(plan)
  const deliveryQ = useDeliveryStatus()
  const createMutation = useCreatePlan()
  const deleteMutation = useDeletePlan()
  const resumeMutation = useResumePlan()
  const swapMutation = useSwapPlanSlot()
  const importMutation = useImportPlanToList()

  const planning = ['queued', 'generating'].includes(plan?.status)
  const busy = createMutation.isPending || deleteMutation.isPending || planning
  const error = createMutation.error?.message || deleteMutation.error?.message

  // Returned promise lets MealCard show its own "Swapping…" state.
  const swap = (slot) => swapMutation.mutateAsync({ planId: plan.id, slot })

  function addAllToList(again) {
    importMutation.mutate({ planId: plan.id, copyId: again ? crypto.randomUUID() : undefined }, {
      onSuccess: (items) => {
        setImportedPlanId(plan.id)
        toast.success(
          items.length > 0
            ? `Added ${items.length} item${items.length === 1 ? '' : 's'} to your shopping list`
            : 'Already imported. Use Add again if you are planning another copy.',
        )
      },
    })
  }

  if (planQ.isPending) return <PageSkeleton />
  if (planQ.isError) return <QueryError query={planQ} title="Couldn’t load your plan" />

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
            <label htmlFor="plan-count">How many meals?</label>
            <input
              id="plan-count"
              type="number"
              min="1"
              max="14"
              value={count}
              onChange={(e) => setCount(e.target.value)}
            />
          </div>
          <button
            className="btn primary big"
            onClick={() => createMutation.mutate({ count: Number(count) || 7, requestId: requestId.current })}
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
          onClick={() => deleteMutation.mutate(plan.id, { onSuccess: () => { requestId.current = crypto.randomUUID(); setImportedPlanId(null) } })}
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

      {planning && <div className="banner info" role="status"><strong>Planning {plan.entries.length} of {plan.requested_count} meals…</strong><p>You can leave this page. Your plan will keep building.</p></div>}
      {plan.status === 'failed' && <div className="banner error" role="alert"><p>{plan.error}</p><button className="btn" disabled={resumeMutation.isPending} onClick={() => resumeMutation.mutate(plan.id)}>Resume remaining meals</button></div>}
      <Bento>
        {/* LEFT: the week's meals, with per-day swap */}
        <BentoItem span={8}>
          <div className="stack">
            {plan.entries.map((entry) => (
              <MealCard
                key={entry.meal.id}
                meal={entry.meal}
                onSwap={planning ? null : () => swap(entry.slot_index)}
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
              planning={planning}
              added={importedPlanId === plan.id}
            />
          </div>
        </BentoItem>
      </Bento>
    </div>
  )
}
