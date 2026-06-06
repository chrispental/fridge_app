import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Camera, Image, Plus } from 'lucide-react'
import ItemTile from '../components/ItemTile.jsx'
import ItemModal from '../components/ItemModal.jsx'
import { api, STORAGE } from '../api/client.js'
import { PageHeader, SegmentedControl, EmptyState, Skeleton } from '../components/ui.jsx'

export default function InventoryPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [modalItem, setModalItem] = useState(null) // null=closed, {}=new, item=edit
  const [fetching, setFetching] = useState(false)
  const [storageFilter, setStorageFilter] = useState('all')

  function load() {
    api.getInventory().then(setItems).catch((e) => setError(e.message))
  }
  useEffect(load, [])

  // Open the add modal if navigated here with { state: { add: true } }. Run once.
  const addHandled = useRef(false)
  useEffect(() => {
    if (location.state?.add && !addHandled.current) {
      addHandled.current = true
      setModalItem({})
      navigate(location.pathname, { replace: true, state: null })
    }
  }, [location.state])

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

  if (!items) {
    return (
      <div className="wide">
        <PageHeader eyebrow="Your fridge" title="Inventory" subtitle="Everything you have on hand, organized by where it lives." />
        <div className="tile-grid">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} height={190} radius={14} />
          ))}
        </div>
      </div>
    )
  }

  // Group into storage sections, in the order defined by STORAGE; drop empty ones.
  const sections = STORAGE.map((s) => ({
    ...s,
    items: items.filter((it) => (it.storage || 'unsorted') === s.value),
  })).filter((s) => s.items.length > 0)

  const missingPhotos = items.some((it) => it.image_url == null)

  // Storage filter options: "All" + only storages that actually have items.
  const filterOptions = [
    { value: 'all', label: 'All' },
    ...sections.map((s) => ({ value: s.value, label: `${s.label} (${s.items.length})` })),
  ]
  const visibleSections =
    storageFilter === 'all' ? sections : sections.filter((s) => s.value === storageFilter)

  return (
    <div className="wide">
      <PageHeader
        eyebrow="Your fridge"
        title={`Inventory (${items.length})`}
        subtitle="Everything you have on hand, organized by where it lives."
      >
        <Link to="/capture" className="btn primary">
          <Camera size={16} strokeWidth={2.2} /> Scan a photo
        </Link>
        {missingPhotos && (
          <button className="ghost" onClick={fetchPhotos} disabled={fetching}>
            <Image size={16} strokeWidth={2.2} /> {fetching ? 'Fetching…' : 'Fetch photos'}
          </button>
        )}
        <button className="ghost" onClick={() => setModalItem({})}>
          <Plus size={16} strokeWidth={2.2} /> Add item
        </button>
      </PageHeader>

      {items.length === 0 ? (
        <EmptyState
          icon={<Camera size={22} strokeWidth={2} />}
          title="Your fridge is empty"
          message="Scan a photo of your fridge to get started, or add items by hand."
          action={
            <Link to="/capture" className="btn primary">
              <Camera size={16} strokeWidth={2.2} /> Scan a photo
            </Link>
          }
        />
      ) : (
        <>
          {filterOptions.length > 1 && (
            <div style={{ marginBottom: 'var(--sp-5)' }}>
              <SegmentedControl
                options={filterOptions}
                value={storageFilter}
                onChange={setStorageFilter}
                scroll
              />
            </div>
          )}

          {visibleSections.map((section) => (
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
        </>
      )}

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
