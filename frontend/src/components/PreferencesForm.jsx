import { useState } from 'react'

const EQUIPMENT_OPTIONS = [
  'stovetop', 'oven', 'microwave', 'air fryer', 'blender',
  'grill', 'slow cooker', 'toaster', 'kettle', 'food processor',
]

const listToText = (l) => (l || []).join(', ')
const textToList = (t) =>
  t.split(',').map((s) => s.trim()).filter(Boolean)

export default function PreferencesForm({ initial, onSubmit, submitLabel = 'Save' }) {
  const [householdSize, setHouseholdSize] = useState(initial?.household_size ?? 1)
  const [allergies, setAllergies] = useState(listToText(initial?.allergies))
  const [dietary, setDietary] = useState(listToText(initial?.dietary_restrictions))
  const [equipment, setEquipment] = useState(initial?.equipment ?? ['stovetop'])
  const [maxComplexity, setMaxComplexity] = useState(initial?.max_complexity ?? 3)
  const [dislikedIng, setDislikedIng] = useState(listToText(initial?.disliked_ingredients))
  const [dislikedCuis, setDislikedCuis] = useState(listToText(initial?.disliked_cuisines))
  const [noRepeat, setNoRepeat] = useState(initial?.no_repeat_days ?? 14)
  const [location, setLocation] = useState(initial?.location ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  function toggleEquip(item) {
    setEquipment((prev) =>
      prev.includes(item) ? prev.filter((x) => x !== item) : [...prev, item],
    )
  }

  async function handleSubmit(ev) {
    ev.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onSubmit({
        household_size: Number(householdSize) || 1,
        allergies: textToList(allergies),
        dietary_restrictions: textToList(dietary),
        equipment,
        max_complexity: Number(maxComplexity),
        disliked_ingredients: textToList(dislikedIng),
        disliked_cuisines: textToList(dislikedCuis),
        no_repeat_days: Number(noRepeat) || 0,
        location: location.trim(),
      })
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="field">
        <label>Household size</label>
        <input
          type="number"
          min="1"
          max="20"
          value={householdSize}
          onChange={(e) => setHouseholdSize(e.target.value)}
        />
      </div>

      <div className="field">
        <label>
          Location{' '}
          <span className="sub">— city or ZIP. Used for grilling weather & delivery.</span>
        </label>
        <input
          type="text"
          placeholder="e.g. Austin, TX or 78701"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
      </div>

      <div className="field">
        <label>
          Allergies <span className="sub">— comma separated. Never suggested.</span>
        </label>
        <input
          type="text"
          placeholder="e.g. peanuts, shellfish"
          value={allergies}
          onChange={(e) => setAllergies(e.target.value)}
        />
      </div>

      <div className="field">
        <label>
          Dietary restrictions <span className="sub">— comma separated</span>
        </label>
        <input
          type="text"
          placeholder="e.g. vegetarian, halal"
          value={dietary}
          onChange={(e) => setDietary(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Kitchen equipment</label>
        <div className="checks">
          {EQUIPMENT_OPTIONS.map((item) => (
            <label key={item}>
              <input
                type="checkbox"
                checked={equipment.includes(item)}
                onChange={() => toggleEquip(item)}
              />
              {item}
            </label>
          ))}
        </div>
      </div>

      <div className="field">
        <label>Maximum meal complexity: {maxComplexity} / 5</label>
        <input
          type="range"
          min="1"
          max="5"
          value={maxComplexity}
          onChange={(e) => setMaxComplexity(e.target.value)}
          style={{ width: '100%' }}
        />
      </div>

      <div className="field">
        <label>
          Disliked ingredients <span className="sub">— comma separated</span>
        </label>
        <input
          type="text"
          placeholder="e.g. olives, blue cheese"
          value={dislikedIng}
          onChange={(e) => setDislikedIng(e.target.value)}
        />
      </div>

      <div className="field">
        <label>
          Disliked cuisines <span className="sub">— comma separated</span>
        </label>
        <input
          type="text"
          placeholder="e.g. very spicy"
          value={dislikedCuis}
          onChange={(e) => setDislikedCuis(e.target.value)}
        />
      </div>

      <div className="field">
        <label>
          Don't repeat a meal for{' '}
          <span className="sub">(days)</span>
        </label>
        <input
          type="number"
          min="0"
          max="365"
          value={noRepeat}
          onChange={(e) => setNoRepeat(e.target.value)}
        />
      </div>

      {error && <div className="banner error">{error}</div>}

      <button type="submit" className="btn primary big" disabled={saving}>
        {saving ? 'Saving…' : submitLabel}
      </button>
    </form>
  )
}
