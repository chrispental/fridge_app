import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, UNITS } from '../api/client.js'

export default function ReviewExtraction() {
  const { batchId } = useParams()
  const navigate = useNavigate()
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api
      .getExtraction(batchId)
      .then((r) => setItems(r.items.map((it, i) => ({ ...it, _key: i }))))
      .catch((e) => setError(e.message))
  }, [batchId])

  function update(key, patch) {
    setItems((prev) => prev.map((it) => (it._key === key ? { ...it, ...patch } : it)))
  }
  function remove(key) {
    setItems((prev) => prev.filter((it) => it._key !== key))
  }
  function addBlank() {
    setItems((prev) => [
      ...prev,
      { _key: `new-${Date.now()}`, name: '', quantity: null, unit: 'piece', category: '', confidence: 1 },
    ])
  }

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      const payload = items
        .filter((it) => it.name.trim())
        .map((it) => ({
          name: it.name,
          quantity: it.quantity,
          unit: it.unit,
          category: it.category || null,
        }))
      await api.confirmExtraction(batchId, payload)
      navigate('/inventory')
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  if (error && !items) return <div className="banner error">{error}</div>
  if (!items) return <div className="loading">Analyzing…</div>

  const namedCount = items.filter((i) => i.name.trim()).length

  return (
    <div>
      <h1>Review detected items</h1>
      <p>
        These are the AI's best guesses — fix anything wrong, remove mistakes,
        then add them to your inventory. ⚠️ marks low-confidence items.
      </p>

      {items.length === 0 && (
        <p className="empty">No items detected. You can add some manually below.</p>
      )}

      <div className="row-gap">
        {items.map((it) => (
          <div
            key={it._key}
            className={`item-row editing ${it.confidence < 0.5 ? 'low-conf' : ''}`}
          >
            <input
              placeholder="name"
              value={it.name}
              onChange={(e) => update(it._key, { name: e.target.value })}
            />
            <input
              type="number"
              step="any"
              placeholder="qty"
              value={it.quantity ?? ''}
              onChange={(e) =>
                update(it._key, {
                  quantity: e.target.value === '' ? null : Number(e.target.value),
                })
              }
            />
            <select
              value={it.unit}
              onChange={(e) => update(it._key, { unit: e.target.value })}
            >
              {UNITS.map((u) => (
                <option key={u} value={u}>{u}</option>
              ))}
            </select>
            <input
              placeholder="category"
              value={it.category || ''}
              onChange={(e) => update(it._key, { category: e.target.value })}
            />
            {it.confidence < 0.5 && (
              <span className="conf-flag" title="Low confidence — please check">⚠️</span>
            )}
            <button className="ghost danger" onClick={() => remove(it._key)}>
              Remove
            </button>
          </div>
        ))}
      </div>

      <button className="ghost" onClick={addBlank} style={{ marginTop: '0.6rem' }}>
        + Add missed item
      </button>

      {error && <div className="banner error">{error}</div>}

      <div className="actions">
        <button className="btn primary big" onClick={confirm} disabled={busy || namedCount === 0}>
          {busy ? 'Saving…' : `Add ${namedCount} item${namedCount === 1 ? '' : 's'} to inventory`}
        </button>
      </div>
    </div>
  )
}
