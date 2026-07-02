import { useState } from 'react'
import { Trash2, Check } from 'lucide-react'
import { UNITS, STORAGE } from '../api/client.js'
import { useAddItem, useDeleteItem, useUpdateItem } from '../api/queries.js'
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

  function save() {
    if (!name.trim()) return
    const body = {
      name,
      quantity: quantity === '' ? null : Number(quantity),
      unit,
      storage,
      category: category || null,
      expires_at: expires || null,
    }
    if (isEdit) updateMutation.mutate({ id: item.id, body })
    else addMutation.mutate(body)
    onClose()
  }

  function remove() {
    deleteMutation.mutate(item.id)
    onClose()
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit item' : 'Add item'}</h2>

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

        <div className="modal-actions">
          {isEdit && (
            <button className="ghost danger" onClick={remove}>
              <Trash2 size={15} strokeWidth={2.2} /> Delete
            </button>
          )}
          <div className="modal-actions-right">
            <button className="ghost" onClick={onClose}>Cancel</button>
            <button className="primary" onClick={save} disabled={!name.trim()}>
              <Check size={15} strokeWidth={2.4} /> {isEdit ? 'Save' : 'Add'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
