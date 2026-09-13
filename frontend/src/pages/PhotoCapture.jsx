import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Camera, RefreshCw } from 'lucide-react'
import { api } from '../api/client.js'
import { PageHeader } from '../components/ui.jsx'
import { usePendingExtractions } from '../api/queries.js'

export default function PhotoCapture() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()
  const pendingQ = usePendingExtractions()
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  function onPick(e) {
    const f = e.target.files?.[0]
    if (!f) return
    if (f.size > 12 * 1024 * 1024) { setError('Choose a photo smaller than 12 MB.'); return }
    setFile(f)
    setPreview(URL.createObjectURL(f))
    setError(null)
  }

  async function scan() {
    if (!file) return
    setBusy(true)
    setError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const result = await api.extractPhoto(fd)
      navigate(`/review/${result.batch_id}`)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  return (
    <div className="narrow">
      <PageHeader
        eyebrow="Inventory"
        title="Scan your fridge"
        subtitle="Choose a clear photo of groceries, a receipt, or your fridge shelves."
      />

      <label className="file-drop">
        <input
          type="file"
          accept="image/*"
          aria-label="Choose a grocery photo"
          onChange={onPick}
          className="sr-only"
        />
        {preview ? (
          <>
            <img src={preview} alt="Selected" className="preview" />
            <span className="btn ghost">
              <RefreshCw size={16} strokeWidth={2.2} /> Retake
            </span>
          </>
        ) : (
          <>
            <div className="drop-ico">
              <Camera size={28} strokeWidth={2} />
            </div>
            <span>Tap to take or choose a photo</span>
          </>
        )}
      </label>

      {error && <div className="banner error">{error}</div>}

      <button
        className="btn primary big block"
        onClick={scan}
        disabled={!file || busy}
      >
        {busy ? 'Analyzing photo…' : 'Analyze photo'}
      </button>

      {busy && (
        <p className="hint">
          The AI is reading your photo — this can take 10–30 seconds.
        </p>
      )}
      {pendingQ.data?.length > 0 && (
        <div className="card" style={{ marginTop: 24 }}>
          <h2>Finish reviewing a scan</h2>
          <ul>{pendingQ.data.map((scan) => <li key={scan.batch_id}><Link to={`/review/${scan.batch_id}`}>Review scan from {new Date(scan.created_at + 'Z').toLocaleString()}</Link></li>)}</ul>
        </div>
      )}
    </div>
  )
}
