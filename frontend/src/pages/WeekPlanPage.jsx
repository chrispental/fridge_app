import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CalendarDays, RefreshCw, AlertCircle } from 'lucide-react'
import MealCard from '../components/MealCard.jsx'
import { api } from '../api/client.js'
import { PageHeader, HeroPanel, Bento, BentoItem } from '../components/ui.jsx'

const fmtDate = (iso) => (iso ? new Date(iso + 'Z').toLocaleDateString() : null)

function ShoppingList({ data }) {
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
          <div className="ingredients">
            {to_buy.map((it, i) => (
              <span key={i} className="chip missing">+ {line(it)}</span>
            ))}
          </div>
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
  const [loading, setLoading] = useState(true)
  const [plan, setPlan] = useState(null)
  const [shopping, setShopping] = useState(null)
  const [count, setCount] = useState(7)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [delivery, setDelivery] = useState(null)

  function loadDelivery() {
    api.getDeliveryStatus().then(setDelivery).catch(() => setDelivery(null))
  }

  function loadShopping(planId) {
    api.getShoppingList(planId).then(setShopping).catch(() => setShopping(null))
  }

  useEffect(() => {
    loadDelivery()
    api
      .getCurrentPlan()
      .then((p) => {
        setPlan(p)
        loadShopping(p.id)
      })
      .catch(() => setPlan(null)) // no plan yet → show the create form
      .finally(() => setLoading(false))
  }, [])

  async function create() {
    setBusy(true)
    setError(null)
    try {
      const p = await api.createPlan(Number(count) || 7)
      setPlan(p)
      loadShopping(p.id)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function newPlan() {
    if (!plan) return
    setBusy(true)
    setError(null)
    try {
      await api.deletePlan(plan.id)
      setPlan(null)
      setShopping(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  // Returned promise lets MealCard show its own "Swapping…" state.
  async function swap(slot) {
    const updated = await api.swapPlanSlot(plan.id, slot)
    setPlan(updated)
    loadShopping(plan.id)
  }

  if (loading) return <div className="loading">Loading…</div>

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
          <button className="btn primary big" onClick={create} disabled={busy}>
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
        <button className="btn ghost" onClick={newPlan} disabled={busy}>
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
                onChanged={() => {
                  loadDelivery()
                  loadShopping(plan.id)
                }}
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
            <ShoppingList data={shopping} />
          </div>
        </BentoItem>
      </Bento>
    </div>
  )
}
