import { useState } from 'react'
import { api, UNITS, STORAGE } from '../api/client.js'

// Add (no id) or edit (has id) a single inventory item. Used by InventoryPage.
export default function ItemModal({ item, onSaved, onDeleted, onClose }) {
  const isEdit = Boolean(item?.id)
  const [name, setName] = useState(item?.name || '')
  const [quantity, setQuantity] = useState(item?.quantity ?? '')
  const [unit, setUnit] = useState(item?.unit || 'piece')
  const [storage, setStorage] = useState(item?.storage || 'fridge')
  const [category, setCategory] = useState(item?.category || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function save() {
    if (!name.trim()) return
    setBusy(true)
    setError(null)
    const body = {
      name,
      quantity: quantity === '' ? null : Number(quantity),
      unit,
      storage,
      category: category || null,
    }
    try {
      const saved = isEdit
        ? await api.updateItem(item.id, body)
        : await api.addItem(body)
      onSaved(saved)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  async function remove() {
    setBusy(true)
    setError(null)
    try {
      await api.deleteItem(item.id)
      onDeleted(item.id)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
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

        {error && <div className="banner error">{error}</div>}

        <div className="modal-actions">
          {isEdit && (
            <button className="ghost danger" onClick={remove} disabled={busy}>
              Delete
            </button>
          )}
          <div className="modal-actions-right">
            <button className="ghost" onClick={onClose} disabled={busy}>Cancel</button>
            <button className="primary" onClick={save} disabled={busy || !name.trim()}>
              {busy ? 'Saving…' : isEdit ? 'Save' : 'Add'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
