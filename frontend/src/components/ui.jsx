// Shared presentational primitives for the "elevated dark + amber" redesign.
// Styling lives in index.css; these components only provide structure + props.
// Icons are passed in as elements (e.g. icon={<Camera size={20} />}) to keep
// this module decoupled from lucide-react.
import { Link } from 'react-router-dom'

export function PageHeader({ eyebrow, title, subtitle, children }) {
  return (
    <div className="page-header">
      <div className="page-header-text">
        {eyebrow && <span className="eyebrow rule">{eyebrow}</span>}
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children && <div className="page-header-actions">{children}</div>}
    </div>
  )
}

export function SectionHeader({ eyebrow, title, action }) {
  return (
    <div className="section-head">
      <div className="section-head-text">
        {eyebrow && <span className="eyebrow rule">{eyebrow}</span>}
        {title && <h2>{title}</h2>}
      </div>
      {action}
    </div>
  )
}

export function Skeleton({ width = '100%', height = 16, radius, className = '', style }) {
  return (
    <div
      className={`skeleton ${className}`}
      style={{ width, height, borderRadius: radius, ...style }}
    />
  )
}

export function EmptyState({ icon, title, message, action }) {
  return (
    <div className="empty">
      {icon && <div className="empty-icon">{icon}</div>}
      {title && <h3>{title}</h3>}
      {message && <p>{message}</p>}
      {action && <div style={{ marginTop: 6 }}>{action}</div>}
    </div>
  )
}

export function SegmentedControl({ options, value, onChange, scroll = false }) {
  return (
    <div className={`segmented${scroll ? ' scroll' : ''}`}>
      {options.map((o) => (
        <button
          key={o.value}
          className={value === o.value ? 'active' : ''}
          onClick={() => onChange(o.value)}
          type="button"
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function StickyActionBar({ info, children }) {
  return (
    <div className="sticky-action-bar">
      {info && <span className="sab-info">{info}</span>}
      {children}
    </div>
  )
}

export function Bento({ children }) {
  return <div className="bento">{children}</div>
}

export function BentoItem({ span = 12, className = '', children }) {
  return (
    <div className={`bento-item ${className}`} style={{ '--span': span }}>
      {children}
    </div>
  )
}

export function HeroPanel({ bgImage, compact = false, className = '', children }) {
  return (
    <section className={`hero-panel${compact ? ' compact' : ''} ${className}`}>
      {bgImage && (
        <div className="hero-bg">
          <img src={bgImage} alt="" aria-hidden="true" />
        </div>
      )}
      <div className="hero-content">{children}</div>
    </section>
  )
}

// Glass stat tile. Renders as a Link when `to` is set, else a plain div.
export function StatCard({ icon, iconTone = '', title, to, children }) {
  const body = (
    <>
      <div className="stat-head">
        {icon && <div className={`stat-ico ${iconTone}`}>{icon}</div>}
        {title && <span className="stat-title">{title}</span>}
      </div>
      {children}
    </>
  )
  return to ? (
    <Link to={to} className="stat-card">{body}</Link>
  ) : (
    <div className="stat-card">{body}</div>
  )
}

// Icon-on-glass action tile. `to` → Link (optionally with router state), else `onClick` → button.
export function QuickAction({ icon, label, sub, to, state, onClick }) {
  const body = (
    <>
      <div className="qa-ico">{icon}</div>
      <div>
        <div className="qa-label">{label}</div>
        {sub && <div className="qa-sub">{sub}</div>}
      </div>
    </>
  )
  return to ? (
    <Link to={to} state={state} className="quick-action">{body}</Link>
  ) : (
    <button type="button" className="quick-action" onClick={onClick}>{body}</button>
  )
}

// Compact, read-only meal preview that links into the Cook surface.
export function MealPreviewCard({ meal, to = '/cook' }) {
  const r = meal.recipe_json || {}
  const ingredients = r.ingredients || []
  const have = ingredients.filter((i) => i.in_stock).length
  return (
    <Link to={to} className="meal-preview">
      <div className="meal-preview-thumb">
        {r.image_url ? <img src={r.image_url} alt="" loading="lazy" /> : '🍽'}
      </div>
      <div className="meal-preview-body">
        <span className="meal-preview-title">{meal.title}</span>
        <span className="meal-preview-meta">
          {r.cuisine && <span>{r.cuisine}</span>}
          {r.cooking_method && <span className="method-chip">{r.cooking_method}</span>}
          {r.estimated_time_minutes && <span>⏱ {r.estimated_time_minutes}m</span>}
          {ingredients.length > 0 && (
            <span>{have}/{ingredients.length} in stock</span>
          )}
        </span>
      </div>
    </Link>
  )
}

// Horizontal scroll of day chips for the current week plan.
export function PlanStrip({ entries = [], toBuyCount = null }) {
  return (
    <div className="plan-strip">
      {entries.map((e) => {
        const r = e.meal.recipe_json || {}
        return (
          <Link key={e.meal.id} to="/plan" className="plan-chip">
            <div className="plan-chip-thumb">
              {r.image_url ? <img src={r.image_url} alt="" loading="lazy" /> : '🍽'}
            </div>
            <div className="plan-chip-body">
              <span className="plan-chip-day">Day {e.slot_index + 1}</span>
              <span className="plan-chip-title">{e.meal.title}</span>
            </div>
          </Link>
        )
      })}
      {toBuyCount != null && toBuyCount > 0 && (
        <Link to="/plan" className="plan-chip add">
          <span>🛒</span>
          <span>{toBuyCount} to buy</span>
        </Link>
      )}
    </div>
  )
}
