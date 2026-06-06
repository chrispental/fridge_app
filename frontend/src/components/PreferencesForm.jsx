import { useState } from 'react'
import {
  Flame, CookingPot, Microwave, Fan, Blend,
  Beef, Soup, Sandwich, Coffee, Salad,
} from 'lucide-react'
import { SectionHeader } from './ui.jsx'

// `value` must match what the backend stores/reads; `label` is display only.
const EQUIPMENT_OPTIONS = [
  { value: 'stovetop', label: 'Stovetop', Icon: Flame },
  { value: 'oven', label: 'Oven', Icon: CookingPot },
  { value: 'microwave', label: 'Microwave', Icon: Microwave },
  { value: 'air fryer', label: 'Air fryer', Icon: Fan },
  { value: 'blender', label: 'Blender', Icon: Blend },
  { value: 'grill', label: 'Grill', Icon: Beef },
  { value: 'slow cooker', label: 'Slow cooker', Icon: Soup },
  { value: 'toaster', label: 'Toaster', Icon: Sandwich },
  { value: 'kettle', label: 'Kettle', Icon: Coffee },
  { value: 'food processor', label: 'Food processor', Icon: Salad },
]

const listToText = (l) => (l || []).join(', ')
const textToList = (t) =>
  t.split(',').map((s) => s.trim()).filter(Boolean)

export default function PreferencesForm({
  initial,
  onSubmit,
  submitLabel = 'Save',
  grouped = false,
  hideSubmit = false,
}) {
  const [householdSize, setHouseholdSize] = useState(initial?.household_size ?? 1)
  const [allergies, setAllergies] = useState(listToText(initial?.allergies))
  const [dietary, setDietary] = useState(listToText(initial?.dietary_restrictions))
  const [equipment, setEquipment] = useState(initial?.equipment ?? ['stovetop'])
  const [maxComplexity, setMaxComplexity] = useState(initial?.max_complexity ?? 3)
  const [dislikedIng, setDislikedIng] = useState(listToText(initial?.disliked_ingredients))
  const [dislikedCuis, setDislikedCuis] = useState(listToText(initial?.disliked_cuisines))
  const [noRepeat, setNoRepeat] = useState(initial?.no_repeat_days ?? 14)
  const [location, setLocation] = useState(initial?.location ?? '')
  const [staples, setStaples] = useState(listToText(initial?.pantry_staples))
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
        pantry_staples: textToList(staples),
      })
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  // ---- Individual fields (shared between grouped + flat layouts) ----
  const householdField = (
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
  )

  const locationField = (
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
  )

  const allergiesField = (
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
  )

  const dietaryField = (
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
  )

  const dislikedIngField = (
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
  )

  const dislikedCuisField = (
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
  )

  const equipmentField = (
    <div className="field">
      <label>Kitchen equipment</label>
      <div className="equip-grid">
        {EQUIPMENT_OPTIONS.map(({ value, label, Icon }) => {
          const on = equipment.includes(value)
          return (
            <button
              type="button"
              key={value}
              className={`equip-chip${on ? ' on' : ''}`}
              onClick={() => toggleEquip(value)}
              aria-pressed={on}
            >
              <Icon size={17} strokeWidth={2} />
              <span>{label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )

  const complexityField = (
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
  )

  const staplesField = (
    <div className="field">
      <label>
        Pantry staples{' '}
        <span className="sub">
          — comma separated. Always assumed on hand, so they're never on your
          shopping list.
        </span>
      </label>
      <input
        type="text"
        placeholder="e.g. salt, pepper, hot sauce"
        value={staples}
        onChange={(e) => setStaples(e.target.value)}
      />
    </div>
  )

  const noRepeatField = (
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
  )

  const errorBanner = error && <div className="banner error">{error}</div>
  const submitButton = !hideSubmit && (
    <button type="submit" className="btn primary big" disabled={saving}>
      {saving ? 'Saving…' : submitLabel}
    </button>
  )

  if (grouped) {
    return (
      <form onSubmit={handleSubmit}>
        <div className="field-group">
          <SectionHeader eyebrow="Household & location" />
          <div className="settings-grid">
            {householdField}
            {locationField}
          </div>
        </div>

        <div className="field-group">
          <SectionHeader eyebrow="Taste & diet" />
          <div className="settings-grid">
            {allergiesField}
            {dietaryField}
            {dislikedIngField}
            {dislikedCuisField}
          </div>
        </div>

        <div className="field-group">
          <SectionHeader eyebrow="Kitchen" />
          {equipmentField}
        </div>

        <div className="field-group">
          <SectionHeader eyebrow="Cooking rules" />
          {complexityField}
          {noRepeatField}
          {staplesField}
        </div>

        {errorBanner}
        {submitButton}
      </form>
    )
  }

  return (
    <form onSubmit={handleSubmit}>
      {householdField}
      {locationField}
      {allergiesField}
      {dietaryField}
      {equipmentField}
      {complexityField}
      {dislikedIngField}
      {dislikedCuisField}
      {staplesField}
      {noRepeatField}

      {errorBanner}
      {submitButton}
    </form>
  )
}
