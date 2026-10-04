import { Carrot, Beef, Milk, Fish, Wheat, CupSoda, Package } from 'lucide-react'
import { expiryInfo } from '../utils/dates.js'
import { formatAmount, isLowStock } from '../utils/quantity.js'

const CATEGORY_ICONS = {
  produce: Carrot, vegetable: Carrot, fruit: Carrot, herb: Carrot,
  meat: Beef, poultry: Beef, protein: Beef,
  dairy: Milk, seafood: Fish, fish: Fish,
  grain: Wheat, pantry: Wheat, bakery: Wheat, bread: Wheat, pasta: Wheat,
  beverage: CupSoda, drink: CupSoda,
}
// Categories are free text ("Grains", "vegetables"); match on the singular form.
const categoryKey = (category) => (category || '').trim().toLowerCase().replace(/s$/, '')

// A single inventory item rendered as a tile. Display-only; clicking opens the
// edit modal (handled by the parent). Category icons keep inventory consistent.
export default function ItemTile({ item, onEdit }) {
  const CategoryIcon = CATEGORY_ICONS[categoryKey(item.category)] || Package
  const lowStock = isLowStock(item)
  const expiry = expiryInfo(item.expires_at)

  return (
    <button className="item-tile" onClick={() => onEdit(item)} title="Edit item">
      {lowStock && <span className="tile-low" role="img" aria-label="Running low" title="Running low" />}
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
          {item.quantity != null ? formatAmount(item.quantity, item.unit) : '—'}
        </span>
        {item.category && <span className="tile-cat">{item.category}</span>}
      </div>
    </button>
  )
}
