import { useEffect, useState } from 'react'
import PreferencesForm from '../components/PreferencesForm.jsx'
import { PageHeader } from '../components/ui.jsx'
import { api } from '../api/client.js'

export default function PreferencesPage() {
  const [initial, setInitial] = useState(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.getPreferences().then(setInitial)
  }, [])

  if (!initial) return <div className="loading">Loading…</div>

  return (
    <div>
      <PageHeader
        eyebrow="Settings"
        title="Preferences"
        subtitle="Tune your household, taste, kitchen, and cooking rules so every suggestion fits you."
      />
      {saved && <div className="banner success">Preferences saved.</div>}
      <PreferencesForm
        initial={initial}
        grouped
        submitLabel="Save preferences"
        onSubmit={async (body) => {
          const updated = await api.updatePreferences(body)
          setInitial(updated)
          setSaved(true)
          setTimeout(() => setSaved(false), 3000)
        }}
      />
    </div>
  )
}
