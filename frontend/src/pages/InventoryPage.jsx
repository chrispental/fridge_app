import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ItemRow from '../components/ItemRow.jsx'
import { api, UNITS, STORAGE } from '../api/client.js'

const BLANK = { name: '', quantity: '', unit: 'piece', category: '', storage: 'fridge' }

export default function InventoryPage() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState(BLANK)

  function load() {
    api.getInventory().then(setItems).catch((e) => setError(e.message))
  }
  useEffect(load, [])

  async function add() {
    if (!draft.name.trim()) return
    try {
      const created = await api.addItem({
        name: draft.name,
        quantity: draft.quantity === '' ? null : Number(draft.quantity),
        unit: draft.unit,
        category: draft.category || null,
        storage: draft.storage,
      })
      setItems([created, ...items])
      setDraft(BLANK)
      setAdding(false)
    } catch (e) {
      alert(e.message)
    }
  }

  if (error) return <div className="banner error">{error}</div>
  if (!items) return <div className="loading">Loading…</div>

  // Group into storage sections, in the order defined by STORAGE; drop empty ones.
  const sections = STORAGE.map((s) => ({
    ...s,
    items: items.filter((it) => (it.storage || 'unsorted') === s.value),
  })).filter((s) => s.items.length > 0)

  return (
    <div>
      <div className="page-head">
        <h1>Inventory ({items.length})</h1>
        <div>
          <Link to="/capture" className="btn primary">📷 Scan a photo</Link>
          <button className="ghost" onClick={() => setAdding((v) => !v)}>
            + Add item
          </button>
        </div>
      </div>

      {adding && (
        <div className="item-row editing">
          <input
            placeholder="name"
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
          <input
            type="number"
            step="any"
            placeholder="qty"
            value={draft.quantity}
            onChange={(e) => setDraft({ ...draft, quantity: e.target.value })}
          />
          <select
            value={draft.unit}
            onChange={(e) => setDraft({ ...draft, unit: e.target.value })}
          >
            {UNITS.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
          <select
            value={draft.storage}
            onChange={(e) => setDraft({ ...draft, storage: e.target.value })}
          >
            {STORAGE.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <input
            placeholder="category"
            value={draft.category}
            onChange={(e) => setDraft({ ...draft, category: e.target.value })}
          />
          <button className="primary" onClick={add}>Add</button>
          <button className="ghost" onClick={() => setAdding(false)}>Cancel</button>
        </div>
      )}

      {items.length === 0 && (
        <p className="empty">
          Your inventory is empty. Scan a photo of your fridge to get started.
        </p>
      )}

      {sections.map((section) => (
        <div key={section.value} className="storage-section">
          <h2 className="storage-head">
            <span className="storage-emoji">{section.emoji}</span>
            {section.label}
            <span className="storage-count">{section.items.length}</span>
          </h2>
          {section.items.map((it) => (
            <ItemRow
              key={it.id}
              item={it}
              onChange={(u) => setItems(items.map((x) => (x.id === u.id ? u : x)))}
              onDelete={(id) => setItems(items.filter((x) => x.id !== id))}
            />
          ))}
        </div>
      ))}
    </div>
  )
}
