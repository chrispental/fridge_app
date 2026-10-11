// Lightweight toast notifications. Components call `toast.success/error/info()`
// directly (module-level bus), so non-React code — like the QueryClient's global
// onError — can fire toasts too. ToastProvider renders the stack via a portal.
import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { CheckCircle2, AlertCircle, Info } from 'lucide-react'

import { listeners } from './toast.js'

const ICONS = {
  success: <CheckCircle2 size={16} strokeWidth={2.2} />,
  error: <AlertCircle size={16} strokeWidth={2.2} />,
  info: <Info size={16} strokeWidth={2.2} />,
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((cur) => cur.filter((t) => t.id !== id))
    clearTimeout(timers.current.get(id))
    timers.current.delete(id)
  }, [])

  useEffect(() => {
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
  }, [dismiss])

  return (
    <>
      {children}
      {createPortal(
        <div className="toast-stack" role="status" aria-live="polite">
          {toasts.map((t) => (
            // Tap anywhere to dismiss; an optional action (e.g. Undo) sits inside.
            <div key={t.id} className={`toast ${t.tone}`} onClick={() => dismiss(t.id)}>
              {ICONS[t.tone]}
              <span>{t.message}</span>
              {t.action && (
                <button
                  type="button"
                  className="toast-action"
                  onClick={(e) => {
                    e.stopPropagation()
                    dismiss(t.id)
                    t.action.onClick()
                  }}
                >
                  {t.action.label}
                </button>
              )}
            </div>
          ))}
        </div>,
        document.body,
      )}
    </>
  )
}
