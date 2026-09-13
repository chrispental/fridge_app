import PreferencesForm from '../components/PreferencesForm.jsx'
import { usePreferences, useUpdatePreferences } from '../api/queries.js'
import { PageSkeleton } from '../components/ui.jsx'
import QueryError from '../components/QueryError.jsx'

export default function Onboarding() {
  const prefsQ = usePreferences()
  const updateMutation = useUpdatePreferences()
  if (prefsQ.isError) return <QueryError query={prefsQ} />

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
          Start with your household, food needs, and kitchen. You can tune
          everything else later in Settings.
        </p>
        <div style={{ marginTop: '1.75rem' }}>
          <PreferencesForm
            initial={prefsQ.data || {}}
            compact
            submitLabel="Get started"
            onSubmit={(body) => updateMutation.mutateAsync(body)}
          />
        </div>
      </div>
    </div>
  )
}
