import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, ChefHat, CalendarDays, Refrigerator, History,
  Settings, Sparkles, MoreHorizontal,
} from 'lucide-react'

// Desktop sidebar menu (Settings lives in the bottom utility group).
const MAIN = [
  { to: '/', label: 'Home', icon: LayoutDashboard, end: true },
  { to: '/cook', label: 'Cook', icon: ChefHat },
  { to: '/plan', label: 'Plan', icon: CalendarDays },
  { to: '/inventory', label: 'Fridge', icon: Refrigerator },
  { to: '/history', label: 'History', icon: History },
]

// Mobile bottom bar: Home · Plan · [FAB=Cook] · Fridge · More(sheet).
const MOBILE_LEFT = [
  { to: '/', label: 'Home', icon: LayoutDashboard, end: true },
  { to: '/plan', label: 'Plan', icon: CalendarDays },
]
const MOBILE_RIGHT = [
  { to: '/inventory', label: 'Fridge', icon: Refrigerator },
]
const MORE = [
  { to: '/history', label: 'History', icon: History },
  { to: '/preferences', label: 'Settings', icon: Settings },
]

export default function Nav() {
  const [moreOpen, setMoreOpen] = useState(false)

  return (
    <>
      {/* ---- Desktop sidebar ---- */}
      <nav className="nav">
        <div className="nav-brand">
          <span className="nav-logo">🍳</span>
          <span className="nav-brand-text">Fridge Chef</span>
        </div>

        <NavLink to="/cook" className="nav-cta">
          <Sparkles size={18} strokeWidth={2.2} />
          New meal
        </NavLink>

        <div className="nav-group">
          <span className="eyebrow">Menu</span>
          <div className="nav-links">
            {MAIN.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? 'active' : '')}>
                <Icon size={19} strokeWidth={2} />
                <span className="nav-label">{label}</span>
              </NavLink>
            ))}
          </div>
        </div>

        <div className="nav-group nav-foot">
          <div className="nav-links">
            <NavLink to="/preferences" className={({ isActive }) => (isActive ? 'active' : '')}>
              <Settings size={19} strokeWidth={2} />
              <span className="nav-label">Settings</span>
            </NavLink>
          </div>
          <div className="nav-profile">
            <div className="nav-avatar">C</div>
            <div className="nav-profile-text">
              <span className="nav-profile-name">Chris</span>
              <span className="nav-profile-sub">Personal kitchen</span>
            </div>
          </div>
        </div>
      </nav>

      {/* ---- Mobile floating bottom bar ---- */}
      {moreOpen && (
        <>
          <div className="mobile-sheet-scrim" onClick={() => setMoreOpen(false)} />
          <div className="mobile-sheet">
            {MORE.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                onClick={() => setMoreOpen(false)}
                className={({ isActive }) => (isActive ? 'active' : '')}
              >
                <Icon size={18} strokeWidth={2} />
                {label}
              </NavLink>
            ))}
          </div>
        </>
      )}

      <div className="mobile-nav">
        {MOBILE_LEFT.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => (isActive ? 'active' : '')}>
            <Icon size={22} strokeWidth={2} />
            <span>{label}</span>
          </NavLink>
        ))}

        <NavLink
          to="/cook"
          className={({ isActive }) => `mobile-fab${isActive ? ' active' : ''}`}
          aria-label="New meal"
        >
          <Sparkles size={24} strokeWidth={2.2} />
        </NavLink>

        {MOBILE_RIGHT.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) => (isActive ? 'active' : '')}>
            <Icon size={22} strokeWidth={2} />
            <span>{label}</span>
          </NavLink>
        ))}

        <button
          type="button"
          className={moreOpen ? 'on' : ''}
          onClick={() => setMoreOpen((v) => !v)}
          aria-label="More"
        >
          <MoreHorizontal size={22} strokeWidth={2} />
          <span>More</span>
        </button>
      </div>
    </>
  )
}
