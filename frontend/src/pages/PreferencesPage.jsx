import PreferencesForm from '../components/PreferencesForm.jsx'
import { PageHeader, PageSkeleton } from '../components/ui.jsx'
import { usePreferences, useUpdatePreferences } from '../api/queries.js'
import { toast } from '../components/Toast.jsx'

export default function PreferencesPage() {
  const prefsQ = usePreferences()
  const updateMutation = useUpdatePreferences()

  if (prefsQ.isPending) return <PageSkeleton />

  return (
    <div>
      <PageHeader
        eyebrow="Settings"
        title="Preferences"
        subtitle="Tune your household, taste, kitchen, and cooking rules so every suggestion fits you."
      />
      <PreferencesForm
        initial={prefsQ.data}
        grouped
        submitLabel="Save preferences"
        onSubmit={async (body) => {
          await updateMutation.mutateAsync(body)
          toast.success('Preferences saved')
        }}
      />
    </div>
  )
}
