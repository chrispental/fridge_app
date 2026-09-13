import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Plus, Trash2, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { api, UNITS, STORAGE } from '../api/client.js'
import { useAuth } from '../auth/useAuth.js'
import { kitchenKey, readStored, writeStored } from '../utils/storage.js'
import { useConfirmExtraction, useExtraction } from '../api/queries.js'
import QueryError from '../components/QueryError.jsx'
import { toast } from '../components/toast.js'
import { PageHeader, StickyActionBar, EmptyState, PageSkeleton } from '../components/ui.jsx'

export default function ReviewExtraction() {
  const { batchId } = useParams()
  const navigate = useNavigate()
  const extractionQ = useExtraction(batchId)
  const confirmMutation = useConfirmExtraction()
  const { session } = useAuth()
  const draftKey = kitchenKey(session?.user?.id, 'scan', batchId)
  const [photo, setPhoto] = useState(null)
  const [photoError, setPhotoError] = useState(false)

  // The fetched proposal seeds an editable local list; the user owns it from
  // the first edit (edits === null means "untouched, show the proposal").
  const [edits, setEdits] = useState(() => {
    const saved = readStored(draftKey, null)
    return Array.isArray(saved) && saved.every((i) => typeof i?.name === 'string') ? saved : null
  })
  useEffect(() => { if (edits) writeStored(draftKey, edits) }, [draftKey, edits])
  useEffect(() => {
    const controller = new AbortController()
    let objectUrl
    api.getExtractionImage(batchId, controller.signal).then((blob) => {
      if (controller.signal.aborted) return
      objectUrl = URL.createObjectURL(blob)
      setPhoto(objectUrl)
    }).catch(() => { if (!controller.signal.aborted) setPhotoError(true) })
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [batchId])
  useEffect(() => {
    if (extractionQ.data?.status === 'confirmed') writeStored(draftKey, null)
  }, [draftKey, extractionQ.data?.status])
  const proposed = extractionQ.data
    ? extractionQ.data.items.map((it, i) => ({ ...it, _key: i }))
    : null
  const items = edits ?? proposed
  const setItems = (fn) => setEdits((prev) => fn(prev ?? proposed))

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
          writeStored(draftKey, null)
          toast.success(`Added ${saved.length} item${saved.length === 1 ? '' : 's'} to your fridge`)
          navigate('/inventory')
        },
      },
    )
  }

  if (extractionQ.isError) return <QueryError query={extractionQ} title="Couldn’t load this scan. Your edits are saved." />
  if (extractionQ.isPending || !items) return <PageSkeleton caption="Analyzing your photo…" />
  if (extractionQ.data?.status === 'confirmed') {
    return <div className="card"><h1>This scan is already saved</h1><Link className="btn primary" to="/inventory">Open inventory</Link></div>
  }
  if (extractionQ.data?.status !== 'pending_review') {
    return <div className="card"><h1>This scan isn't ready to review</h1><Link className="btn" to="/capture">Start another scan</Link></div>
  }

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

      <div className="scan-review-layout">
        <aside className="scan-review-photo">
          {photo ? <img src={photo} alt="Original grocery photo for comparison" /> : <p>{photoError ? 'Photo unavailable. You can still review the items.' : 'Loading your photo…'}</p>}
          <p className="hint">Edits are saved in this browser until you confirm.</p>
        </aside>
      <div className="row-gap">
        {items.map((it) => (
          <div
            key={it._key}
            className={`item-row editing ${it.confidence < 0.5 ? 'low-conf' : ''}`}
          >
            <input
              aria-label={`Item name, row ${items.indexOf(it) + 1}`}
              placeholder="name"
              value={it.name}
              onChange={(e) => update(it._key, { name: e.target.value })}
            />
            <input
              type="number"
              min="0"
              aria-label={`Quantity for ${it.name || 'new item'}`}
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
              aria-label={`Unit for ${it.name || 'new item'}`}
              value={it.unit}
              onChange={(e) => update(it._key, { unit: e.target.value })}
            >
              {UNITS.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
            <select
              aria-label={`Storage for ${it.name || 'new item'}`}
              value={it.storage || 'unsorted'}
              onChange={(e) => update(it._key, { storage: e.target.value })}
            >
              {STORAGE.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
            <input
              aria-label={`Category for ${it.name || 'new item'}`}
              placeholder="category"
              value={it.category || ''}
              onChange={(e) => update(it._key, { category: e.target.value })}
            />
            <input
              type="date"
              aria-label={`Expiry for ${it.name || 'new item'}`}
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
