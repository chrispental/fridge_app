import { useState } from 'react'
import { api, UNITS, STORAGE } from '../api/client.js'

export default function ItemRow({ item, onChange, onDelete }) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(item.name)
  const [quantity, setQuantity] = useState(item.quantity ?? '')
  const [unit, setUnit] = useState(item.unit || 'unknown')
  const [category, setCategory] = useState(item.category || '')
  const [storage, setStorage] = useState(item.storage || 'unsorted')
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    try {
      const updated = await api.updateItem(item.id, {
        name,
        quantity: quantity === '' ? null : Number(quantity),
        unit,
        category: category || null,
        storage,
      })
      onChange(updated)
      setEditing(false)
    } catch (e) {
      alert(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setBusy(true)
    try {
      await api.deleteItem(item.id)
      onDelete(item.id)
    } catch (e) {
      alert(e.message)
      setBusy(false)
    }
  }

  if (editing) {
    return (
      <div className="item-row editing">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="name" />
        <input
          type="number"
          step="any"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder="qty"
        />
        <select value={unit} onChange={(e) => setUnit(e.target.value)}>
          {UNITS.map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
        <select value={storage} onChange={(e) => setStorage(e.target.value)}>
          {STORAGE.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
        <input
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          placeholder="category"
        />
        <button className="primary" onClick={save} disabled={busy}>Save</button>
        <button className="ghost" onClick={() => setEditing(false)} disabled={busy}>
          Cancel
        </button>
      </div>
    )
  }

  return (
    <div className="item-row">
      <span className="item-name">{item.name}</span>
      <span className="item-qty">
        {item.quantity != null ? `${item.quantity} ${item.unit}` : '—'}
      </span>
      {item.category && <span className="item-cat">{item.category}</span>}
      <button className="ghost" onClick={() => setEditing(true)}>Edit</button>
      <button className="ghost danger" onClick={remove} disabled={busy}>Delete</button>
    </div>
  )
}
