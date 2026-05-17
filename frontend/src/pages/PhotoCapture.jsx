import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'

export default function PhotoCapture() {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  function onPick(e) {
    const f = e.target.files?.[0]
    if (!f) return
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
    <div>
      <h1>Add inventory from a photo</h1>
      <p>Take or upload a clear photo of your fridge or pantry shelves.</p>

      <label className="file-drop">
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onChange={onPick}
          hidden
        />
        {preview ? (
          <img src={preview} alt="Selected" className="preview" />
        ) : (
          <span>📷 Tap to take or choose a photo</span>
        )}
      </label>

      {error && <div className="banner error">{error}</div>}

      <button className="btn primary big" onClick={scan} disabled={!file || busy}>
        {busy ? 'Analyzing photo…' : 'Analyze photo'}
      </button>

      {busy && (
        <p className="hint">
          The AI is reading your photo — this can take 10–30 seconds.
        </p>
      )}
    </div>
  )
}
