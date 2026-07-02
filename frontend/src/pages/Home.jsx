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

  const inventoryQ = useInventory()
  const planQ = useCurrentPlan()
  const suggestedQ = useMeals('suggested')
  const deliveryQ = useDeliveryStatus()
  const prefsQ = usePreferences()
  const shoppingQ = usePlanShoppingList(planQ.data?.id)

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
  const go = (run, useIdea) =>
    navigate('/cook', { state: { run, idea: useIdea ? idea.trim() : '' } })

  const heroImg = suggested?.find((m) => m.recipe_json?.image_url)?.recipe_json?.image_url

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

  return (
    <div className="wide">
      <Bento>
        {/* A. Hero */}
        <BentoItem span={8} className="tall">
          <HeroPanel bgImage={heroImg}>
            <div className="home-hero-greeting">
              <span className="eyebrow rule">{greeting()}{name ? `, ${name}` : ''}</span>
              <h1 className="display">What's for dinner?</h1>
            </div>
            <p>Tell me what you're craving, or let me surprise you with something from your fridge.</p>
            <div className="hero-field">
              <textarea
                rows={2}
                className="idea-input"
                placeholder="e.g. “something with chicken & spinach”, “a cozy soup”, “quick Thai noodles”…"
                value={idea}
                onChange={(e) => setIdea(e.target.value)}
              />
              <div className="hero-actions">
                <button
                  className="btn primary big"
                  onClick={() => go(true, true)}
                  disabled={!hasIdea}
                  title={hasIdea ? '' : 'Type an idea first, or hit Surprise me'}
                >
                  <Sparkles size={18} strokeWidth={2.2} /> Use my idea
                </button>
                <button className="btn big" onClick={() => go(true, false)}>
                  <Dices size={18} strokeWidth={2.2} /> Surprise me
                </button>
              </div>
            </div>
          </HeroPanel>
        </BentoItem>

        {/* B. Delivery status */}
        <BentoItem span={4}>
          <StatCard
            icon={<Truck size={20} strokeWidth={2} />}
            iconTone={deliveryAvailable ? 'success' : ''}
            title="Weekly delivery"
            to={hasLocation ? '/history' : '/preferences'}
          >
            {loading ? (
              <Skeleton height={42} />
            ) : !hasLocation ? (
              <p>Set a location to enable once-a-week delivery.</p>
            ) : deliveryAvailable ? (
              <>
                <div className="stat-row">
                  <span className="status-dot on" />
                  <span className="stat-big" style={{ fontSize: '1.35rem' }}>Available</span>
                </div>
                <p>Order one meal this week instead of cooking.</p>
              </>
            ) : (
              <>
                <div className="stat-row">
                  <span className="status-dot warn" />
                  <span className="stat-big" style={{ fontSize: '1.35rem' }}>Used</span>
                </div>
                <p>Next available {fmtDate(delivery?.next_available_at) || 'soon'}.</p>
              </>
            )}
          </StatCard>
        </BentoItem>

        {/* C. Fridge at a glance */}
        <BentoItem span={4}>
          <StatCard icon={<Snowflake size={20} strokeWidth={2} />} title="Your fridge" to="/inventory">
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

        {/* D. Tonight's picks */}
        <BentoItem span={7}>
          <div className="card" style={{ padding: 20 }}>
            <SectionHeader
              eyebrow="Tonight's picks"
              title="Fresh ideas"
              action={<Link to="/cook" className="see-all">See all <ArrowRight size={13} strokeWidth={2.4} style={{ verticalAlign: '-2px' }} /></Link>}
            />
            {loading ? (
              <div className="stack" style={{ gap: 10 }}>
                <Skeleton height={88} radius={14} />
                <Skeleton height={88} radius={14} />
              </div>
            ) : suggested && suggested.length > 0 ? (
              <div className="stack" style={{ gap: 10 }}>
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

        {/* E. This week's plan */}
        <BentoItem span={5}>
          <div className="card" style={{ padding: 20 }}>
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
    </div>
  )
}
