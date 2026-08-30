import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, ChefHat, CalendarDays, Refrigerator, History,
  Settings, Sparkles, MoreHorizontal, ShoppingCart, BarChart3, LogOut,
} from 'lucide-react'
import { usePreferences } from '../api/queries.js'
import { useAuth } from '../auth/useAuth.js'

// Desktop sidebar menu (Settings lives in the bottom utility group).
const MAIN = [
  { to: '/', label: 'Home', icon: LayoutDashboard, end: true },
  { to: '/cook', label: 'Cook', icon: ChefHat },
  { to: '/plan', label: 'Plan', icon: CalendarDays },
  { to: '/inventory', label: 'Fridge', icon: Refrigerator },
  { to: '/shopping', label: 'Shopping', icon: ShoppingCart },
  { to: '/history', label: 'History', icon: History },
  { to: '/insights', label: 'Insights', icon: BarChart3 },
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
  { to: '/shopping', label: 'Shopping', icon: ShoppingCart },
  { to: '/history', label: 'History', icon: History },
  { to: '/insights', label: 'Insights', icon: BarChart3 },
  { to: '/preferences', label: 'Settings', icon: Settings },
]

export default function Nav() {
  const [moreOpen, setMoreOpen] = useState(false)
  const prefsQ = usePreferences()
  const { authEnabled, session, signOut } = useAuth()
  const name = prefsQ.data?.name?.trim() || 'Chef'
  const initial = name.charAt(0).toUpperCase()
  // Cloud mode shows who is signed in; local mode keeps the single-kitchen label.
  const sub = authEnabled ? session?.user?.email || 'Signed in' : 'Personal kitchen'

  return (
    <>
      {/* ---- Desktop sidebar ---- */}
      <nav className="nav">
        <div className="nav-brand">
          <img className="nav-logo" src="/logo-mark.png" alt="" width="52" height="52" />
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
            <div className="nav-avatar">{initial}</div>
            <div className="nav-profile-text">
              <span className="nav-profile-name">{name}</span>
              <span className="nav-profile-sub" title={sub}>{sub}</span>
            </div>
            {authEnabled && (
              <button
                type="button"
                className="nav-signout"
                onClick={signOut}
                aria-label="Sign out"
                title="Sign out"
              >
                <LogOut size={17} strokeWidth={2} />
              </button>
            )}
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
            {authEnabled && (
              <button
                type="button"
                className="mobile-sheet-signout"
                onClick={() => {
                  setMoreOpen(false)
                  signOut()
                }}
              >
                <LogOut size={18} strokeWidth={2} />
                Sign out
              </button>
            )}
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
