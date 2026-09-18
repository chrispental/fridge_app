import { Carrot, Beef, Milk, Fish, Wheat, CupSoda, Package } from 'lucide-react'
import { expiryInfo } from '../utils/dates.js'

// A single inventory item rendered as a tile. Display-only; clicking opens the
// edit modal (handled by the parent). Category icons keep inventory consistent.
export default function ItemTile({ item, onEdit }) {
  const CategoryIcon = ({ produce: Carrot, meat: Beef, dairy: Milk, seafood: Fish, grain: Wheat, pantry: Wheat, beverage: CupSoda })[item.category?.toLowerCase()] || Package
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
        <span className="tile-photo-empty"><CategoryIcon size={40} strokeWidth={1.5} aria-hidden="true" /></span>
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
