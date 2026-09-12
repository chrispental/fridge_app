import { Sun, Moon, Monitor } from 'lucide-react'
import { setTheme, useTheme } from '../theme.js'

const OPTIONS = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

export default function ThemePicker() {
  const theme = useTheme()
  return (
    <div className="theme-picker" role="group" aria-label="Color theme">
      {OPTIONS.map(({ value, label, icon: Icon }) => (
        <button key={value} type="button" aria-pressed={theme === value} onClick={() => setTheme(value)}>
          <Icon size={16} aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </div>
  )
}
