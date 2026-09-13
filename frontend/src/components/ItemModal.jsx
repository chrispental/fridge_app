import { useId, useState } from 'react'
import { Trash2, Check } from 'lucide-react'
import { UNITS, STORAGE } from '../api/client.js'
import { useAddItem, useDeleteItem, useUpdateItem } from '../api/queries.js'
import { useDialog } from './useDialog.js'
import { localDatePlus } from '../utils/dates.js'

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
  const isEdit = Boolean(item?.id)
  const [name, setName] = useState(item?.name || '')
  const [quantity, setQuantity] = useState(item?.quantity ?? '')
  const [unit, setUnit] = useState(item?.unit || 'piece')
  const [storage, setStorage] = useState(item?.storage || 'fridge')
  const [category, setCategory] = useState(item?.category || '')
  const [expires, setExpires] = useState(item?.expires_at || '')

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
    try { await deleteMutation.mutateAsync(item.id); onClose() }
    catch { /* Error is rendered below. */ }
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
            <select value={storage} onChange={(e) => setStorage(e.target.value)}>
              {STORAGE.map((s) => (
                <option key={s.value} value={s.value}>{s.emoji} {s.label}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Category</span>
            <input
              value={category}
              placeholder="e.g. dairy"
              onChange={(e) => setCategory(e.target.value)}
            />
          </label>
        </div>

        <label className="field">
          <span>Expires <span className="sub">— optional</span></span>
          <input
            type="date"
            value={expires}
            onChange={(e) => setExpires(e.target.value)}
          />
          <div className="expiry-chips">
            {EXPIRY_CHIPS.map((c) => (
              <button
                key={c.days}
                type="button"
                className="chip-toggle"
                onClick={() => setExpires(localDatePlus(c.days))}
              >
                {c.label}
              </button>
            ))}
            {expires && (
              <button type="button" className="chip-toggle" onClick={() => setExpires('')}>
                Clear
              </button>
            )}
          </div>
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
