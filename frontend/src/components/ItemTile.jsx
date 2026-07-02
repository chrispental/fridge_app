import { expiryInfo } from '../utils/dates.js'

// A single inventory item rendered as a tile. Display-only; clicking opens the
// edit modal (handled by the parent). `image_url`: null = not fetched yet,
// "" = fetched but none found, otherwise a Brave thumbnail URL.
export default function ItemTile({ item, onEdit }) {
  const hasPhoto = Boolean(item.image_url)
  const lowStock = item.quantity != null && item.quantity <= 1
  const expiry = expiryInfo(item.expires_at)

  return (
    <button className="item-tile" onClick={() => onEdit(item)} title="Edit item">
      {lowStock && <span className="tile-low" />}
      {expiry && (
        <span className={`tile-expiry${expiry.expired ? ' expired' : ''}`}>
          {expiry.expired ? 'expired' : `⏳ ${expiry.label}`}
        </span>
      )}
      <div className="tile-photo">
        {hasPhoto ? (
          <img src={item.image_url} alt={item.name} loading="lazy" />
        ) : (
          <span className="tile-photo-empty">🥫</span>
        )}
      </div>
      <div className="tile-name">{item.name}</div>
      <div className="tile-meta">
        <span className="tile-qty">
          {item.quantity != null ? `${item.quantity} ${item.unit}` : '—'}
        </span>
        {item.category && <span className="tile-cat">{item.category}</span>}
      </div>
    </button>
  )
}
