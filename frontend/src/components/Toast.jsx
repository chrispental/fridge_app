// Lightweight toast notifications. Components call `toast.success/error/info()`
// directly (module-level bus), so non-React code — like the QueryClient's global
// onError — can fire toasts too. ToastProvider renders the stack via a portal.
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { CheckCircle2, AlertCircle, Info } from 'lucide-react'

const listeners = new Set()
let nextId = 1

function emit(tone, message, opts = {}) {
  listeners.forEach((fn) => fn({ id: nextId++, tone, message, ...opts }))
}

export const toast = {
  success: (message, opts) => emit('success', message, opts),
  error: (message, opts) => emit('error', message, opts),
  info: (message, opts) => emit('info', message, opts),
}

const ICONS = {
  success: <CheckCircle2 size={16} strokeWidth={2.2} />,
  error: <AlertCircle size={16} strokeWidth={2.2} />,
  info: <Info size={16} strokeWidth={2.2} />,
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())

  useEffect(() => {
    const dismiss = (id) => {
      setToasts((cur) => cur.filter((t) => t.id !== id))
      clearTimeout(timers.current.get(id))
      timers.current.delete(id)
    }
    const onToast = (t) => {
      setToasts((cur) => [...cur.slice(-3), t]) // cap the stack at 4
      timers.current.set(t.id, setTimeout(() => dismiss(t.id), t.duration ?? 4000))
    }
    listeners.add(onToast)
    const pending = timers.current
    return () => {
      listeners.delete(onToast)
      pending.forEach(clearTimeout)
      pending.clear()
    }
  }, [])

  return (
    <>
      {children}
      {createPortal(
        <div className="toast-stack" role="status" aria-live="polite">
          {toasts.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`toast ${t.tone}`}
              onClick={() =>
                setToasts((cur) => cur.filter((x) => x.id !== t.id))
              }
            >
              {ICONS[t.tone]}
              <span>{t.message}</span>
            </button>
          ))}
        </div>,
        document.body,
      )}
    </>
  )
}
