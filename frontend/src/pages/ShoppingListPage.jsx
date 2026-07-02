import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, ShoppingCart, Trash2, PackageCheck, Eraser } from 'lucide-react'
import { UNITS } from '../api/client.js'
import {
  useAddShoppingItem, useCheckedToInventory, useClearChecked,
  useDeleteShoppingItem, useShoppingList, useUpdateShoppingItem,
} from '../api/queries.js'
import { toast } from '../components/Toast.jsx'
import {
  PageHeader, EmptyState, Skeleton, StickyActionBar,
} from '../components/ui.jsx'

function ShopRow({ item, onToggle, onDelete }) {
  return (
    <div className={`shop-row${item.checked ? ' checked' : ''}`}>
      <label className="shop-row-main">
        <input
          type="checkbox"
          checked={item.checked}
          onChange={() => onToggle(item)}
        />
        <span className="shop-row-name">{item.name}</span>
        {item.quantity != null && (
          <span className="shop-row-qty">
            {item.quantity}{item.unit !== 'unknown' ? ` ${item.unit}` : ''}
          </span>
        )}
        {item.source !== 'manual' && (
          <span className="shop-row-src">{item.source === 'plan' ? 'from plan' : 'from meal'}</span>
        )}
      </label>
      <button className="ghost danger shop-row-del" onClick={() => onDelete(item)} aria-label={`Remove ${item.name}`}>
        <Trash2 size={15} strokeWidth={2.2} />
      </button>
    </div>
  )
}

export default function ShoppingListPage() {
  const listQ = useShoppingList()
  const addMutation = useAddShoppingItem()
  const updateMutation = useUpdateShoppingItem()
  const deleteMutation = useDeleteShoppingItem()
  const clearMutation = useClearChecked()
  const toInventoryMutation = useCheckedToInventory()

  const [name, setName] = useState('')
  const [quantity, setQuantity] = useState('')
  const [unit, setUnit] = useState('piece')

  function add(ev) {
    ev.preventDefault()
    if (!name.trim()) return
    addMutation.mutate({
      name: name.trim(),
      quantity: quantity === '' ? null : Number(quantity),
      unit,
    })
    setName('')
    setQuantity('')
  }

  const toggle = (item) =>
    updateMutation.mutate({ id: item.id, body: { checked: !item.checked } })
  const remove = (item) => deleteMutation.mutate(item.id)

  function moveToInventory() {
    toInventoryMutation.mutate(undefined, {
      onSuccess: (created) =>
        toast.success(
          `Added ${created.length} item${created.length === 1 ? '' : 's'} to your fridge`,
        ),
    })
  }

  if (listQ.isPending) {
    return (
      <div>
        <PageHeader eyebrow="Shopping" title="Shopping list" subtitle="Check things off as you shop, then move them into your fridge." />
        <div className="stack" style={{ gap: 10 }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} height={52} radius={12} />
          ))}
        </div>
      </div>
    )
  }
  if (listQ.isError) return <div className="banner error">{listQ.error.message}</div>

  const items = listQ.data || []
  const toBuy = items.filter((it) => !it.checked)
  const checked = items.filter((it) => it.checked)

  return (
    <div>
      <PageHeader
        eyebrow="Shopping"
        title="Shopping list"
        subtitle="Check things off as you shop, then move them into your fridge in one tap."
      />

      <form className="shop-add" onSubmit={add}>
        <input
          className="shop-add-name"
          placeholder="Add something… e.g. lemons"
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-label="Item name"
        />
        <input
          className="shop-add-qty"
          type="number"
          step="any"
          min="0"
          placeholder="qty"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          aria-label="Quantity"
        />
        <select value={unit} onChange={(e) => setUnit(e.target.value)} aria-label="Unit">
          {UNITS.map((u) => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
        <button type="submit" className="btn primary" disabled={!name.trim()}>
          <Plus size={16} strokeWidth={2.2} /> Add
        </button>
      </form>

      {items.length === 0 ? (
        <EmptyState
          icon={<ShoppingCart size={22} strokeWidth={2} />}
          title="Nothing to buy"
          message="Add items above, or send missing ingredients here from any meal or your weekly plan."
          action={<Link to="/plan" className="btn primary">Open your plan</Link>}
        />
      ) : (
        <>
          <div className="shop-group">
            <h3>To buy ({toBuy.length})</h3>
            {toBuy.length === 0 ? (
              <p className="hint">All checked off — nice work. 🎉</p>
            ) : (
              <div className="stack" style={{ gap: 8 }}>
                {toBuy.map((it) => (
                  <ShopRow key={it.id} item={it} onToggle={toggle} onDelete={remove} />
                ))}
              </div>
            )}
          </div>

          {checked.length > 0 && (
            <div className="shop-group">
              <h3>In your cart ({checked.length})</h3>
              <div className="stack" style={{ gap: 8 }}>
                {checked.map((it) => (
                  <ShopRow key={it.id} item={it} onToggle={toggle} onDelete={remove} />
                ))}
              </div>
            </div>
          )}

          {checked.length > 0 && (
            <StickyActionBar info={`${checked.length} item${checked.length === 1 ? '' : 's'} in your cart`}>
              <button
                className="ghost"
                onClick={() => clearMutation.mutate()}
                disabled={clearMutation.isPending}
              >
                <Eraser size={15} strokeWidth={2.2} /> Clear checked
              </button>
              <button
                className="btn primary"
                onClick={moveToInventory}
                disabled={toInventoryMutation.isPending}
              >
                <PackageCheck size={16} strokeWidth={2.2} />
                {toInventoryMutation.isPending
                  ? 'Moving…'
                  : `Add ${checked.length} to my fridge`}
              </button>
            </StickyActionBar>
          )}
        </>
      )}
    </div>
  )
}
