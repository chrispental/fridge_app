import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Sparkles, Dices, Truck } from 'lucide-react'
import MealCard from '../components/MealCard.jsx'
import { api } from '../api/client.js'
import { PageHeader, HeroPanel, EmptyState, Skeleton } from '../components/ui.jsx'

const fmtDate = (iso) => (iso ? new Date(iso + 'Z').toLocaleDateString() : null)

export default function SuggestMeal() {
  const location = useLocation()
  const navigate = useNavigate()
  const [meals, setMeals] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [delivery, setDelivery] = useState(null)
  const [idea, setIdea] = useState(location.state?.idea || '')

  function loadDelivery() {
    api.getDeliveryStatus().then(setDelivery).catch(() => setDelivery(null))
  }
  useEffect(() => {
    loadDelivery()
    // Show the most recent suggestions by default (unless auto-running from Home).
    if (!location.state?.run) {
      api
        .getMeals('suggested')
        .then((m) => setMeals((m || []).slice(0, 6)))
        .catch(() => {})
    }
  }, [])

  async function suggest(useIdea, ideaText) {
    setBusy(true)
    setError(null)
    setMeals(null)
    try {
      const text = ideaText != null ? ideaText : idea.trim()
      setMeals(await api.suggestMeals({ count: 5, idea: useIdea ? text : null }))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  // Auto-run a suggestion when navigated here with router state (from Home).
  // Guard with a ref so it runs only once, then clear the consumed state.
  const ranFromState = useRef(false)
  useEffect(() => {
    if (ranFromState.current) return
    if (location.state?.run) {
      ranFromState.current = true
      const stateIdea = location.state.idea || ''
      const useIdea = stateIdea.trim().length > 0
      navigate(location.pathname, { replace: true, state: null })
      suggest(useIdea, useIdea ? stateIdea.trim() : null)
    }
  }, [location.state])

  const deliveryAvailable = delivery ? !delivery.used : true
  const nextDeliveryDate = fmtDate(delivery?.next_available_at)
  const hasIdea = idea.trim().length > 0

  return (
    <div>
      <PageHeader
        eyebrow="Cook"
        title="What should I eat?"
        subtitle="Tell me what you're in the mood for, or let me surprise you."
      />

      <HeroPanel compact>
        <div className="hero-field" style={{ maxWidth: '100%' }}>
          <textarea
            rows={2}
            className="idea-input"
            placeholder="What are you craving? e.g. “something with chicken & spinach”, “a cozy soup”, “quick Thai noodles”…"
            value={idea}
            onChange={(e) => setIdea(e.target.value)}
          />
          <div className="hero-actions">
            <button
              className="btn primary big"
              onClick={() => suggest(true)}
              disabled={busy || !hasIdea}
              title={hasIdea ? '' : 'Type an idea first, or hit Surprise me'}
            >
              <Sparkles size={18} strokeWidth={2.2} /> {busy ? 'Thinking…' : 'Use my idea'}
            </button>
            <button className="btn big" onClick={() => suggest(false)} disabled={busy}>
              <Dices size={18} strokeWidth={2.2} /> Surprise me
            </button>
          </div>
          {delivery && (
            <p className="hint" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Truck size={14} strokeWidth={2.2} />
              {deliveryAvailable
                ? 'Weekly delivery available — order one meal instead of cooking.'
                : `Weekly delivery used — next available ${nextDeliveryDate}.`}
            </p>
          )}
        </div>
      </HeroPanel>

      {error && (
        <div className="banner error">
          {error}
          <div style={{ marginTop: '0.5rem' }}>
            <Link to="/inventory">Check your inventory</Link> ·{' '}
            <Link to="/preferences">adjust preferences</Link>
          </div>
        </div>
      )}

      {busy && (
        <p className="hint" style={{ marginTop: 18 }}>Asking the chef — this can take 10–30 seconds.</p>
      )}

      <div className="meal-results">
        {busy &&
          [0, 1, 2].map((i) => <Skeleton key={i} height={360} radius={20} />)}

        {!busy &&
          meals &&
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

      {!busy && meals && meals.length === 0 && (
        <EmptyState
          icon={<Sparkles size={22} strokeWidth={2} />}
          title="No suggestions"
          message="Try adding more to your fridge, then ask again."
          action={<Link to="/inventory" className="btn primary">Go to inventory</Link>}
        />
      )}
    </div>
  )
}
