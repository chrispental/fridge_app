export const listeners = new Set()
let nextId = 1

function emit(tone, message, opts = {}) {
  listeners.forEach((fn) => fn({ id: nextId++, tone, message, ...opts }))
}

export const toast = {
  success: (message, opts) => emit('success', message, opts),
  error: (message, opts) => emit('error', message, opts),
  info: (message, opts) => emit('info', message, opts),
}
