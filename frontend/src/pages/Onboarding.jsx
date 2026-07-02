import PreferencesForm from '../components/PreferencesForm.jsx'
import { usePreferences, useUpdatePreferences } from '../api/queries.js'
import { PageSkeleton } from '../components/ui.jsx'

export default function Onboarding() {
  const prefsQ = usePreferences()
  const updateMutation = useUpdatePreferences()

  if (prefsQ.isPending) {
    return (
      <div className="onboarding">
        <div className="onboarding-card">
          <PageSkeleton />
        </div>
      </div>
    )
  }

  return (
    <div className="onboarding">
      <div className="onboarding-card">
        <div className="onboarding-badge">
          <img src="/logo-mark.png" alt="" width="76" height="76" />
        </div>
        <h1>Welcome to Fridge Chef</h1>
        <p>
          A few quick questions so every meal we suggest fits you, your
          kitchen, and your taste. You can change all of this later.
        </p>
        <div style={{ marginTop: '1.75rem' }}>
          <PreferencesForm
            initial={prefsQ.data || {}}
            submitLabel="Get started"
            onSubmit={(body) => updateMutation.mutateAsync(body)}
          />
        </div>
      </div>
    </div>
  )
}
