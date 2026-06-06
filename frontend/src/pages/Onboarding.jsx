import { useEffect, useState } from 'react'
import { ChefHat } from 'lucide-react'
import PreferencesForm from '../components/PreferencesForm.jsx'
import { api } from '../api/client.js'

export default function Onboarding({ onDone }) {
  const [initial, setInitial] = useState(null)

  useEffect(() => {
    api.getPreferences().then(setInitial).catch(() => setInitial({}))
  }, [])

  if (!initial) return <div className="loading">Loading…</div>

  return (
    <div className="onboarding">
      <div className="onboarding-card">
        <div className="onboarding-badge">
          <ChefHat size={30} strokeWidth={2} />
        </div>
        <h1>Welcome to Fridge Chef</h1>
        <p>
          A few quick questions so every meal we suggest fits you, your
          kitchen, and your taste. You can change all of this later.
        </p>
        <div style={{ marginTop: '1.75rem' }}>
          <PreferencesForm
            initial={initial}
            submitLabel="Get started"
            onSubmit={async (body) => {
              await api.updatePreferences(body)
              onDone()
            }}
          />
        </div>
      </div>
    </div>
  )
}
