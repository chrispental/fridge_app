import { useId } from 'react'

export default function ServingPicker({ value, onChange, disabled = false }) {
  const id = useId()
  return (
    <div className="serving-picker">
      <label htmlFor={id}>Cooking for</label>
      <select id={id} value={value} onChange={(e) => onChange(Number(e.target.value))} disabled={disabled}>
        {Array.from({ length: 20 }, (_, i) => i + 1).map((n) => (
          <option key={n} value={n}>{n} {n === 1 ? 'person' : 'people'}</option>
        ))}
      </select>
      <span className="hint">Ingredient amounts will match.</span>
    </div>
  )
}
