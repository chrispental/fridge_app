import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Sparkles, Dices, Truck, Camera, CalendarDays, Plus,
  SlidersHorizontal, ArrowRight, Snowflake, AlertCircle, Timer,
} from 'lucide-react'
import { STORAGE } from '../api/client.js'
import {
  useCurrentPlan, useDeliveryStatus, useInventory, useMeals,
  usePlanShoppingList, usePreferences,
} from '../api/queries.js'
import {
  HeroPanel, Bento, BentoItem, StatCard, QuickAction,
  SectionHeader, MealPreviewCard, PlanStrip, EmptyState, Skeleton,
} from '../components/ui.jsx'
import { expiryInfo } from '../utils/dates.js'
import ServingPicker from '../components/ServingPicker.jsx'
import QueryError from '../components/QueryError.jsx'

const fmtDate = (iso) => (iso ? new Date(iso + 'Z').toLocaleDateString() : null)

function greeting() {
  const h = new Date().getHours()
  if (h < 5) return 'Late night'
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

export default function Home() {
  const navigate = useNavigate()
  const [idea, setIdea] = useState('')
  const [servingsOverride, setServingsOverride] = useState(null)

  const inventoryQ = useInventory()
  const planQ = useCurrentPlan()
  const suggestedQ = useMeals('suggested')
  const deliveryQ = useDeliveryStatus()
  const prefsQ = usePreferences()
  const shoppingQ = usePlanShoppingList(planQ.data)

  const loading =
    inventoryQ.isPending || planQ.isPending || suggestedQ.isPending ||
    deliveryQ.isPending || prefsQ.isPending

  const inventory = inventoryQ.data
  const plan = planQ.data
  const suggested = suggestedQ.data
  const delivery = deliveryQ.data
  const prefs = prefsQ.data
  const toBuy = shoppingQ.data ? (shoppingQ.data.to_buy || []).length : null

  const hasIdea = idea.trim().length > 0
  const servings = servingsOverride ?? prefs?.household_size ?? 1
  const go = (run, useIdea) =>
    navigate('/cook', { state: { run, idea: useIdea ? idea.trim() : '', servings } })

  // ---- Fridge-at-a-glance derived values ----
  const items = inventory || []
  const storageCounts = STORAGE.map((s) => ({
    ...s,
    count: items.filter((it) => (it.storage || 'unsorted') === s.value).length,
  })).filter((s) => s.count > 0)
  const lowItems = items.filter((it) => it.quantity != null && it.quantity <= 1).slice(0, 3)
  const expiringItems = items
    .map((it) => ({ ...it, _expiry: expiryInfo(it.expires_at) }))
    .filter((it) => it._expiry)
    .sort((a, b) => a._expiry.days - b._expiry.days)

  const deliveryAvailable = delivery ? !delivery.used : false
  const hasLocation = Boolean(prefs?.location)
  const name = prefs?.name?.trim()

  if (prefsQ.isError) return <QueryError query={prefsQ} title="Couldn't load your serving preferences" />

  return (
    <div className="wide home-page">
      <Bento>
        {/* A. Hero */}
        <BentoItem span={12}>
          <HeroPanel>
            <div className="home-hero-greeting">
              <span className="eyebrow rule">{greeting()}{name ? `, ${name}` : ''}</span>
              <h1 className="display">What's for dinner?</h1>
            </div>
            <p>Start with a craving. We'll take it from fridge to table.</p>
            <div className="hero-field">
              <textarea
                rows={2}
                className="idea-input"
                aria-label="What would you like to cook?"
                placeholder="Chicken & spinach, a cozy soup, quick noodles…"
                value={idea}
                onChange={(e) => setIdea(e.target.value)}
              />
              <ServingPicker value={servings} onChange={setServingsOverride} disabled={!prefs} />
              <div className="hero-actions">
                <button
                  className={`btn big${hasIdea ? ' primary' : ''}`}
                  onClick={() => go(true, true)}
                  disabled={!hasIdea || !prefs}
                  title={hasIdea ? '' : 'Type an idea first, or hit Surprise me'}
                >
                  <Sparkles size={18} strokeWidth={2.2} /> Use my idea
                </button>
                <button className={`btn big${!hasIdea ? ' primary' : ''}`} onClick={() => go(true, false)} disabled={!prefs}>
                  <Dices size={18} strokeWidth={2.2} /> Surprise me
                </button>
              </div>
            </div>
          </HeroPanel>
        </BentoItem>

        {/* D. Tonight's picks */}
        <BentoItem span={12}>
          <div className="home-picks">
            <SectionHeader
              eyebrow="Tonight's picks"
              title="Something delicious awaits"
              action={<Link to="/cook" className="see-all">See all <ArrowRight size={13} strokeWidth={2.4} style={{ verticalAlign: '-2px' }} /></Link>}
            />
            {loading ? (
              <div className="home-meals">
                <Skeleton height={88} radius={14} />
                <Skeleton height={88} radius={14} />
              </div>
            ) : suggested && suggested.length > 0 ? (
              <div className="home-meals">
                {suggested.slice(0, 3).map((m) => (
                  <MealPreviewCard key={m.id} meal={m} />
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<Sparkles size={22} strokeWidth={2} />}
                title="No ideas yet"
                message="Hit “Surprise me” above to get tonight's suggestions."
              />
            )}
          </div>
        </BentoItem>

        {/* C2. Expiring soon — only when something needs attention */}
        {!loading && expiringItems.length > 0 && (
          <BentoItem span={12}>
            <StatCard
              icon={<Timer size={20} strokeWidth={2} />}
              iconTone="warn"
              title="Use these first"
              to="/inventory"
            >
              <div className="ingredients" style={{ margin: 0 }}>
                {expiringItems.slice(0, 6).map((it) => (
                  <span
                    key={it.id}
                    className={`chip ${it._expiry.expired ? 'missing' : 'warn'}`}
                  >
                    {it.name} · {it._expiry.label}
                  </span>
                ))}
                {expiringItems.length > 6 && (
                  <span className="chip">+{expiringItems.length - 6} more</span>
                )}
              </div>
              <p style={{ marginTop: 8 }}>
                Meal suggestions will prioritize these ingredients.
              </p>
            </StatCard>
          </BentoItem>
        )}

        {/* E. This week's plan */}
        <BentoItem span={8}>
          <div className="card">
            <SectionHeader
              eyebrow="This week"
              title="Your plan"
              action={<Link to="/plan" className="see-all">Open <ArrowRight size={13} strokeWidth={2.4} style={{ verticalAlign: '-2px' }} /></Link>}
            />
            {loading ? (
              <Skeleton height={124} radius={14} />
            ) : plan?.entries?.length > 0 ? (
              <PlanStrip entries={plan.entries} toBuyCount={toBuy} />
            ) : (
              <EmptyState
                icon={<CalendarDays size={22} strokeWidth={2} />}
                title="No plan yet"
                message="Plan a few days of meals and get one shopping list."
                action={<Link to="/plan" className="btn primary">Plan your week</Link>}
              />
            )}
          </div>
        </BentoItem>

        {/* C. Fridge at a glance */}
        <BentoItem span={4}>
          <StatCard icon={<Snowflake size={20} strokeWidth={2} />} title="Your fridge">
            {loading ? (
              <Skeleton height={92} />
            ) : items.length === 0 ? (
              <p>Your fridge is empty — scan a photo to get started.</p>
            ) : (
              <>
                <div className="stat-row">
                  <span className="stat-big">{items.length}</span>
                  <span className="caption">items on hand</span>
                </div>
                {storageCounts.length > 0 && (
                  <div className="mini-stats">
                    {storageCounts.slice(0, 4).map((s) => (
                      <div key={s.value} className="mini-stat">
                        <span>{s.emoji}</span> <b>{s.count}</b> {s.label}
                      </div>
                    ))}
                  </div>
                )}
                {lowItems.length > 0 && (
                  <div className="ingredients" style={{ margin: 0 }}>
                    {lowItems.map((it) => (
                      <span key={it.id} className="chip missing">
                        <AlertCircle size={12} strokeWidth={2.4} style={{ verticalAlign: '-2px' }} /> {it.name} low
                      </span>
                    ))}
                  </div>
                )}
              </>
            )}
            <div className="stat-foot">
              <Link to="/inventory" className="see-all">Manage fridge <ArrowRight size={13} strokeWidth={2.4} style={{ verticalAlign: '-2px' }} /></Link>
            </div>
          </StatCard>
        </BentoItem>

        {/* F. Quick actions */}
        <BentoItem span={12}>
          <div className="quick-actions">
            <QuickAction icon={<Camera size={20} strokeWidth={2} />} label="Scan photo" sub="Fill your fridge" to="/capture" />
            <QuickAction icon={<CalendarDays size={20} strokeWidth={2} />} label="Plan week" sub="Batch your meals" to="/plan" />
            <QuickAction icon={<Plus size={20} strokeWidth={2} />} label="Add item" sub="Quick entry" to="/inventory" state={{ add: true }} />
            <QuickAction icon={<SlidersHorizontal size={20} strokeWidth={2} />} label="Adjust taste" sub="Tune suggestions" to="/preferences" />
          </div>
        </BentoItem>
      </Bento>
      {!loading && (
        <Link className="home-delivery" to={hasLocation ? '/history' : '/preferences'}>
          <Truck size={20} />
          <span>
            <strong>A night off from cooking</strong>
            {!hasLocation ? 'Set your location to explore weekly delivery.' : deliveryAvailable
              ? 'Your weekly delivery is available whenever you need it.'
              : `Next available ${fmtDate(delivery?.next_available_at) || 'soon'}.`}
          </span>
          <ArrowRight size={18} />
        </Link>
      )}
    </div>
  )
}
