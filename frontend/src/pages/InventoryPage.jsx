import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import ItemTile from '../components/ItemTile.jsx'
import ItemModal from '../components/ItemModal.jsx'
import { api, STORAGE } from '../api/client.js'

export default function InventoryPage() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [modalItem, setModalItem] = useState(null) // null=closed, {}=new, item=edit
  const [fetching, setFetching] = useState(false)

  function load() {
    api.getInventory().then(setItems).catch((e) => setError(e.message))
  }
  useEffect(load, [])

  async function fetchPhotos() {
    setFetching(true)
    try {
      await api.backfillImages()
      load()
    } catch (e) {
      alert(e.message)
    } finally {
      setFetching(false)
    }
  }

  if (error) return <div className="banner error">{error}</div>
  if (!items) return <div className="loading">Loading…</div>

  // Group into storage sections, in the order defined by STORAGE; drop empty ones.
  const sections = STORAGE.map((s) => ({
    ...s,
    items: items.filter((it) => (it.storage || 'unsorted') === s.value),
  })).filter((s) => s.items.length > 0)

  const missingPhotos = items.some((it) => it.image_url == null)

  return (
    <div>
      <div className="page-head">
        <h1>Inventory ({items.length})</h1>
        <div>
          <Link to="/capture" className="btn primary">📷 Scan a photo</Link>
          {missingPhotos && (
            <button className="ghost" onClick={fetchPhotos} disabled={fetching}>
              {fetching ? 'Fetching…' : '🖼 Fetch photos'}
            </button>
          )}
          <button className="ghost" onClick={() => setModalItem({})}>+ Add item</button>
        </div>
      </div>

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
          <div className="tile-grid">
            {section.items.map((it) => (
              <ItemTile key={it.id} item={it} onEdit={setModalItem} />
            ))}
          </div>
        </div>
      ))}

      {modalItem && (
        <ItemModal
          item={modalItem}
          onClose={() => setModalItem(null)}
          onSaved={() => {
            setModalItem(null)
            load()
          }}
          onDeleted={() => {
            setModalItem(null)
            load()
          }}
        />
      )}
    </div>
  )
}
