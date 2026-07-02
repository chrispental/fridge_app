import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Plus, Trash2, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { UNITS, STORAGE } from '../api/client.js'
import { useConfirmExtraction, useExtraction } from '../api/queries.js'
import { toast } from '../components/Toast.jsx'
import { PageHeader, StickyActionBar, EmptyState, PageSkeleton } from '../components/ui.jsx'

export default function ReviewExtraction() {
  const { batchId } = useParams()
  const navigate = useNavigate()
  const extractionQ = useExtraction(batchId)
  const confirmMutation = useConfirmExtraction()

  // The fetched proposal seeds an editable local list; the user owns it from there.
  const [items, setItems] = useState(null)
  useEffect(() => {
    if (extractionQ.data && items === null) {
      setItems(extractionQ.data.items.map((it, i) => ({ ...it, _key: i })))
    }
  }, [extractionQ.data]) // eslint-disable-line react-hooks/exhaustive-deps

  function update(key, patch) {
    setItems((prev) => prev.map((it) => (it._key === key ? { ...it, ...patch } : it)))
  }
  function remove(key) {
    setItems((prev) => prev.filter((it) => it._key !== key))
  }
  function addBlank() {
    setItems((prev) => [
      ...prev,
      { _key: `new-${Date.now()}`, name: '', quantity: null, unit: 'piece', category: '', storage: 'fridge', expires_at: null, confidence: 1 },
    ])
  }

  function confirm() {
    const payload = items
      .filter((it) => it.name.trim())
      .map((it) => ({
        name: it.name,
        quantity: it.quantity,
        unit: it.unit,
        category: it.category || null,
        storage: it.storage || 'unsorted',
        expires_at: it.expires_at || null,
      }))
    confirmMutation.mutate(
      { batchId, items: payload },
      {
        onSuccess: (saved) => {
          toast.success(`Added ${saved.length} item${saved.length === 1 ? '' : 's'} to your fridge`)
          navigate('/inventory')
        },
      },
    )
  }

  if (extractionQ.isError && !items) {
    return <div className="banner error">{extractionQ.error.message}</div>
  }
  if (!items) return <PageSkeleton caption="Analyzing your photo…" />

  const namedCount = items.filter((i) => i.name.trim()).length
  const busy = confirmMutation.isPending

  return (
    <div>
      <PageHeader
        eyebrow="Inventory"
        title="Review detected items"
        subtitle="These are the AI's best guesses — fix anything wrong, remove mistakes, then add them to your inventory. ⚠️ marks low-confidence items. Expiry dates are rough estimates."
      />

      {items.length === 0 && (
        <EmptyState
          icon={<AlertTriangle size={22} strokeWidth={2} />}
          title="No items detected"
          message="You can add some manually below."
        />
      )}

      <div className="row-gap">
        {items.map((it) => (
          <div
            key={it._key}
            className={`item-row editing ${it.confidence < 0.5 ? 'low-conf' : ''}`}
          >
            <input
              placeholder="name"
              value={it.name}
              onChange={(e) => update(it._key, { name: e.target.value })}
            />
            <input
              type="number"
              step="any"
              placeholder="qty"
              value={it.quantity ?? ''}
              onChange={(e) =>
                update(it._key, {
                  quantity: e.target.value === '' ? null : Number(e.target.value),
                })
              }
            />
            <select
              value={it.unit}
              onChange={(e) => update(it._key, { unit: e.target.value })}
            >
              {UNITS.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
            <select
              value={it.storage || 'unsorted'}
              onChange={(e) => update(it._key, { storage: e.target.value })}
            >
              {STORAGE.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
            <input
              placeholder="category"
              value={it.category || ''}
              onChange={(e) => update(it._key, { category: e.target.value })}
            />
            <input
              type="date"
              title="Expiry date (optional)"
              value={it.expires_at || ''}
              onChange={(e) => update(it._key, { expires_at: e.target.value || null })}
            />
            {it.confidence < 0.5 && (
              <span className="conf-flag" title="Low confidence — please check">⚠️</span>
            )}
            <button className="ghost danger" onClick={() => remove(it._key)}>
              <Trash2 size={15} strokeWidth={2.2} style={{ verticalAlign: '-3px' }} /> Remove
            </button>
          </div>
        ))}
      </div>

      <button className="ghost" onClick={addBlank} style={{ marginTop: '0.6rem' }}>
        <Plus size={16} strokeWidth={2.4} style={{ verticalAlign: '-3px' }} /> Add missed item
      </button>

      {confirmMutation.isError && (
        <div className="banner error">{confirmMutation.error.message}</div>
      )}

      <StickyActionBar info={`${namedCount} item${namedCount === 1 ? '' : 's'} ready`}>
        <button className="btn primary big" onClick={confirm} disabled={busy || namedCount === 0}>
          <CheckCircle2 size={18} strokeWidth={2.2} />
          {busy ? 'Saving…' : `Add ${namedCount} item${namedCount === 1 ? '' : 's'} to inventory`}
        </button>
      </StickyActionBar>
    </div>
  )
}
