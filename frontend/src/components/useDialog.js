import { useEffect, useRef } from 'react'

// Native modal dialogs contain keyboard focus and make the background inert.
export function useDialog(onClose) {
  const ref = useRef(null)
  useEffect(() => {
    const dialog = ref.current
    const before = document.activeElement
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    dialog.showModal()
    return () => {
      dialog.close()
      document.body.style.overflow = overflow
      before?.focus?.()
    }
  }, [])
  useEffect(() => {
    const dialog = ref.current
    const cancel = (event) => { event.preventDefault(); onClose() }
    dialog.addEventListener('cancel', cancel)
    return () => dialog.removeEventListener('cancel', cancel)
  }, [onClose])
  return ref
}
