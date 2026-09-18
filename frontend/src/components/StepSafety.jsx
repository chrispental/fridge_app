import { TriangleAlert } from 'lucide-react'
import { stepSafety } from '../utils/stepSafety.js'

export default function StepSafety({ steps, index }) {
  const warnings = stepSafety(steps, index)
  if (!warnings.length) return null
  return (
    <aside className="step-safety" aria-label="Cooking safety">
      <TriangleAlert size={18} aria-hidden="true" />
      <div>{warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>
    </aside>
  )
}
