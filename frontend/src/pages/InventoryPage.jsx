import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Camera, Image, Plus, Search } from 'lucide-react'
import ItemTile from '../components/ItemTile.jsx'
import ItemModal from '../components/ItemModal.jsx'
import { STORAGE } from '../api/client.js'
import { useBackfillImages, useInventory } from '../api/queries.js'
import { toast } from '../components/Toast.jsx'
import { PageHeader, SegmentedControl, EmptyState, Skeleton } from '../components/ui.jsx'

const SORTS = [
  { value: 'newest', label: 'Newest' },
  { value: 'name', label: 'A–Z' },
  { value: 'low', label: 'Low stock' },
  { value: 'expiry', label: 'Expiring' },
]

// "newest" keeps the API's newest-first order.
const COMPARATORS = {
  newest: null,
  name: (a, b) => a.name.localeCompare(b.name),
  low: (a, b) => (a.quantity ?? Infinity) - (b.quantity ?? Infinity),
  expiry: (a, b) => (a.expires_at || '9999-12-31').localeCompare(b.expires_at || '9999-12-31'),
}

export default function InventoryPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const inventoryQ = useInventory()
  const backfill = useBackfillImages()
  const [modalItem, setModalItem] = useState(null) // null=closed, {}=new, item=edit
  const [storageFilter, setStorageFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState('newest')

  // Open the add modal if navigated here with { state: { add: true } }. Run once.
  const addHandled = useRef(false)
  useEffect(() => {
    if (location.state?.add && !addHandled.current) {
      addHandled.current = true
      setModalItem({})
      navigate(location.pathname, { replace: true, state: null })
    }
  }, [location.state])

  function fetchPhotos() {
    backfill.mutate(undefined, {
      onSuccess: () => toast.success('Photos updated'),
    })
  }

  if (inventoryQ.isError) {
    return <div className="banner error">{inventoryQ.error.message}</div>
  }

  if (inventoryQ.isPending) {
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

  const items = inventoryQ.data || []

  // Search filters by name or category; sort applies within each storage section.
  const needle = search.trim().toLowerCase()
  const matched = needle
    ? items.filter(
        (it) =>
          it.name.toLowerCase().includes(needle) ||
          (it.category || '').toLowerCase().includes(needle),
      )
    : items

  const cmp = COMPARATORS[sort]
  const sections = STORAGE.map((s) => {
    const sectionItems = matched.filter((it) => (it.storage || 'unsorted') === s.value)
    return { ...s, items: cmp ? [...sectionItems].sort(cmp) : sectionItems }
  }).filter((s) => s.items.length > 0)

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
          <button className="ghost" onClick={fetchPhotos} disabled={backfill.isPending}>
            <Image size={16} strokeWidth={2.2} /> {backfill.isPending ? 'Fetching…' : 'Fetch photos'}
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
          <div className="inv-toolbar">
            <div className="search-box">
              <Search size={15} strokeWidth={2.2} />
              <input
                type="search"
                placeholder="Search your fridge…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="Search inventory"
              />
            </div>
            <SegmentedControl options={SORTS} value={sort} onChange={setSort} />
          </div>

          {filterOptions.length > 2 && (
            <div style={{ marginBottom: 'var(--sp-5)' }}>
              <SegmentedControl
                options={filterOptions}
                value={storageFilter}
                onChange={setStorageFilter}
                scroll
              />
            </div>
          )}

          {matched.length === 0 ? (
            <EmptyState
              icon={<Search size={22} strokeWidth={2} />}
              title="No matches"
              message={`Nothing in your fridge matches “${search.trim()}”.`}
            />
          ) : (
            visibleSections.map((section) => (
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
            ))
          )}
        </>
      )}

      {modalItem && (
        <ItemModal item={modalItem} onClose={() => setModalItem(null)} />
      )}
    </div>
  )
}
