import { useId, useState } from 'react'
import { UNITS } from '../api/client.js'
import { useUpdateShoppingItem } from '../api/queries.js'
import { useDialog } from './useDialog.js'

export default function ShoppingItemModal({ item, onClose }) {
  const ref = useDialog(onClose)
  const titleId = useId()
  const [name, setName] = useState(item.name)
  const [quantity, setQuantity] = useState(item.quantity ?? '')
  const [unit, setUnit] = useState(item.unit)
  const mutation = useUpdateShoppingItem()

  async function save(event) {
    event.preventDefault()
    if (!name.trim()) return
    try {
      await mutation.mutateAsync({ id: item.id, body: {
        name: name.trim(), quantity: quantity === '' ? null : Number(quantity), unit,
      } })
      onClose()
    } catch { /* Keep edits available to retry. */ }
  }

  return (
    <dialog ref={ref} className="modal" aria-labelledby={titleId}>
      <form onSubmit={save}>
        <h2 id={titleId}>Edit shopping item</h2>
        <p className="hint">Enter the amount you plan to buy or actually bought. This amount will be added to inventory.</p>
        <label className="field"><span>Name</span><input autoFocus value={name} onChange={(e) => setName(e.target.value)} required /></label>
        <div className="modal-row">
          <label className="field"><span>Quantity</span><input type="number" min="0" step="any" value={quantity} placeholder="Unknown" onChange={(e) => setQuantity(e.target.value)} /></label>
          <label className="field"><span>Unit</span><select value={unit} onChange={(e) => setUnit(e.target.value)}>{UNITS.map((u) => <option key={u} value={u}>{u}</option>)}</select></label>
        </div>
        {mutation.error && <p className="banner error" role="alert">{mutation.error.message}</p>}
        <div className="modal-actions">
          <div className="modal-actions-right">
            <button type="button" className="ghost" onClick={onClose} disabled={mutation.isPending}>Cancel</button>
            <button type="submit" className="primary" disabled={mutation.isPending || !name.trim()}>{mutation.isPending ? 'Saving…' : 'Save'}</button>
          </div>
        </div>
      </form>
    </dialog>
  )
}
