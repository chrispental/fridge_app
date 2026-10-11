import { useState } from 'react'
import { Download } from 'lucide-react'
import ThemePicker from '../components/ThemePicker.jsx'
import { api } from '../api/client.js'
import { localDatePlus } from '../utils/dates.js'
import PreferencesForm from '../components/PreferencesForm.jsx'
import { PageHeader, PageSkeleton } from '../components/ui.jsx'
import { usePreferences, useUpdatePreferences } from '../api/queries.js'
import { toast } from '../components/toast.js'
import QueryError from '../components/QueryError.jsx'

// Saves the export blob through a temporary link; nothing leaves the browser.
async function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default function PreferencesPage() {
  const prefsQ = usePreferences()
  const updateMutation = useUpdatePreferences()
  const [exporting, setExporting] = useState(false)

  async function exportData() {
    setExporting(true)
    try {
      const blob = await api.exportData()
      await downloadBlob(blob, `fridge-chef-export-${localDatePlus(0)}.json`)
      toast.success('Your kitchen data is downloading')
    } catch (e) {
      toast.error(e.message)
    } finally {
      setExporting(false)
    }
  }

  if (prefsQ.isPending) return <PageSkeleton />
  if (prefsQ.isError) return <QueryError query={prefsQ} />

  return (
    <div>
      <PageHeader
        eyebrow="Settings"
        title="Preferences"
        subtitle="Tune your household, taste, kitchen, and cooking rules so every suggestion fits you."
      />
      <section className="field-group appearance-settings">
        <h2>Appearance</h2>
        <p>Choose a theme, or follow your device. Saved automatically on this browser.</p>
        <ThemePicker />
      </section>
      <PreferencesForm
        initial={prefsQ.data}
        grouped
        submitLabel="Save preferences"
        onSubmit={async (body) => {
          await updateMutation.mutateAsync(body)
          toast.success('Preferences saved')
        }}
      />
      <section className="field-group data-settings">
        <h2>Your data</h2>
        <p>
          Download everything in your kitchen as one JSON file: preferences, inventory,
          meal history, your recipe book, shopping list, and plans. Photos aren't included.
        </p>
        <button type="button" className="btn" onClick={exportData} disabled={exporting}>
          <Download size={16} strokeWidth={2.2} /> {exporting ? 'Preparing…' : 'Download my data'}
        </button>
      </section>
    </div>
  )
}
