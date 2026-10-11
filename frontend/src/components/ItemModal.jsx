import { useId, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Trash2, Check } from 'lucide-react'
import { api, UNITS, STORAGE } from '../api/client.js'
import { useAddItem, useDeleteItem, useUpdateItem } from '../api/queries.js'
import { useDialog } from './useDialog.js'
import { toast } from './toast.js'
import { localDatePlus } from '../utils/dates.js'
import { CATEGORIES, estimateExpiry } from '../utils/expiry.js'

const EXPIRY_CHIPS = [
  { label: '+3 days', days: 3 },
  { label: '+1 week', days: 7 },
  { label: '+2 weeks', days: 14 },
  { label: '+1 month', days: 30 },
]

// Add (no id) or edit (has id) a single inventory item. Saves are optimistic:
// the modal closes immediately and errors roll back with a toast.
export default function ItemModal({ item, onClose }) {
  const dialogRef = useDialog(onClose)
  const titleId = useId()
  const categoryListId = useId()
  const queryClient = useQueryClient()
  const isEdit = Boolean(item?.id)
  const [name, setName] = useState(item?.name || '')
  const [quantity, setQuantity] = useState(item?.quantity ?? '')
  const [unit, setUnit] = useState(item?.unit || 'piece')
  const [storage, setStorage] = useState(item?.storage || 'fridge')
  const [category, setCategory] = useState(item?.category || '')
  const [expires, setExpires] = useState(item?.expires_at || '')
  // New items get a shelf-life estimate from category + storage until the user
  // sets a date themselves; the hint below the field says it is an estimate.
  const [expiryAuto, setExpiryAuto] = useState(false)
  const expiryTouched = useRef(false)

  function suggestExpiry(nextCategory, nextStorage) {
    if (isEdit || expiryTouched.current) return
    const estimate = estimateExpiry(nextCategory, nextStorage)
    setExpires(estimate || '')
    setExpiryAuto(Boolean(estimate))
  }
  function setExpiresManually(value) {
    expiryTouched.current = true
    setExpiryAuto(false)
    setExpires(value)
  }

  const addMutation = useAddItem()
  const updateMutation = useUpdateItem()
  const deleteMutation = useDeleteItem()

  async function save(event) {
    event.preventDefault()
    if (!name.trim()) return
    const body = {
      name,
      quantity: quantity === '' ? null : Number(quantity),
      unit,
      storage,
      category: category || null,
      expires_at: expires || null,
    }
    try {
      if (isEdit) await updateMutation.mutateAsync({ id: item.id, body })
      else await addMutation.mutateAsync(body)
      onClose()
    } catch { /* Keep the user's input available for retry. */ }
  }

  async function remove() {
    // Snapshot first: an undo re-creates the item (new id, same details).
    const snapshot = {
      name: item.name, quantity: item.quantity ?? null, unit: item.unit,
      storage: item.storage, category: item.category || null, expires_at: item.expires_at || null,
    }
    try {
      await deleteMutation.mutateAsync(item.id)
      onClose()
      toast.success(`Removed ${item.name}`, {
        duration: 8000,
        action: {
          label: 'Undo',
          onClick: () =>
            api.addItem(snapshot)
              .then(() => queryClient.invalidateQueries({ queryKey: ['inventory'] }))
              .then(() => toast.success(`${snapshot.name} is back in your fridge`))
              .catch((e) => toast.error(e.message)),
        },
      })
    } catch { /* Error is rendered below. */ }
  }
  const busy = addMutation.isPending || updateMutation.isPending || deleteMutation.isPending
  const error = addMutation.error || updateMutation.error || deleteMutation.error

  return (
    <dialog ref={dialogRef} className="modal" aria-labelledby={titleId}>
      <form onSubmit={save}>
        <h2 id={titleId}>{isEdit ? 'Edit item' : 'Add item'}</h2>

        <label className="field">
          <span>Name</span>
          <input
            autoFocus
            value={name}
            placeholder="e.g. cheddar cheese"
            onChange={(e) => setName(e.target.value)}
          />
        </label>

        <div className="modal-row">
          <label className="field">
            <span>Quantity</span>
            <input
              type="number"
              step="any"
              min="0"
              value={quantity}
              placeholder="qty"
              onChange={(e) => setQuantity(e.target.value)}
            />
          </label>
          <label className="field">
            <span>Unit</span>
            <select value={unit} onChange={(e) => setUnit(e.target.value)}>
              {UNITS.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="modal-row">
          <label className="field">
            <span>Storage</span>
            <select
              value={storage}
              onChange={(e) => {
                setStorage(e.target.value)
                suggestExpiry(category, e.target.value)
              }}
            >
              {STORAGE.map((s) => (
                <option key={s.value} value={s.value}>{s.emoji} {s.label}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Category</span>
            <input
              value={category}
              list={categoryListId}
              placeholder="e.g. dairy"
              onChange={(e) => {
                setCategory(e.target.value)
                suggestExpiry(e.target.value, storage)
              }}
            />
            <datalist id={categoryListId}>
              {CATEGORIES.map((c) => <option key={c} value={c} />)}
            </datalist>
          </label>
        </div>

        <label className="field">
          <span>Expires <span className="sub">— optional</span></span>
          <input
            type="date"
            value={expires}
            onChange={(e) => setExpiresManually(e.target.value)}
          />
          <div className="expiry-chips">
            {EXPIRY_CHIPS.map((c) => (
              <button
                key={c.days}
                type="button"
                className="chip-toggle"
                onClick={() => setExpiresManually(localDatePlus(c.days))}
              >
                {c.label}
              </button>
            ))}
            {expires && (
              <button type="button" className="chip-toggle" onClick={() => setExpiresManually('')}>
                Clear
              </button>
            )}
          </div>
          {expiryAuto && expires && (
            <span className="hint">Estimated from the category — change it if the label says otherwise.</span>
          )}
        </label>

        {error && <p className="banner error" role="alert">{error.message}</p>}
        <div className="modal-actions">
          {isEdit && (
            <button type="button" className="ghost danger" onClick={remove} disabled={busy}>
              <Trash2 size={15} strokeWidth={2.2} /> Delete
            </button>
          )}
          <div className="modal-actions-right">
            <button type="button" className="ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary" disabled={busy || !name.trim()}>
              <Check size={15} strokeWidth={2.4} /> {busy ? 'Saving…' : isEdit ? 'Save' : 'Add'}
            </button>
          </div>
        </div>
      </form>
    </dialog>
  )
}
