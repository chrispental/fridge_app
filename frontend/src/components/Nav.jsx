import { NavLink } from 'react-router-dom'
import { ChefHat, Refrigerator, History, Settings } from 'lucide-react'

const LINKS = [
  { to: '/', label: 'Cook', icon: ChefHat, end: true },
  { to: '/inventory', label: 'Fridge', icon: Refrigerator },
  { to: '/history', label: 'History', icon: History },
  { to: '/preferences', label: 'Settings', icon: Settings },
]

export default function Nav() {
  return (
    <nav className="nav">
      <div className="nav-brand">
        <span className="nav-logo">🍳</span>
        <span className="nav-brand-text">Fridge Chef</span>
      </div>

      <div className="nav-links">
        {LINKS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => (isActive ? 'active' : '')}
          >
            <Icon size={19} strokeWidth={2} />
            <span className="nav-label">{label}</span>
          </NavLink>
        ))}
      </div>

      <div className="nav-profile">
        <div className="nav-avatar">C</div>
        <div className="nav-profile-text">
          <span className="nav-profile-name">Chris</span>
          <span className="nav-profile-sub">Personal kitchen</span>
        </div>
      </div>
    </nav>
  )
}
