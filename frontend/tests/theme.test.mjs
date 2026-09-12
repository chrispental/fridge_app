import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const source = readFileSync(new URL('../src/theme.js', import.meta.url), 'utf8')
  .replace("import { useSyncExternalStore } from 'react'", '')
  .replaceAll('export function', 'function')
const bootstrap = readFileSync(new URL('../index.html', import.meta.url), 'utf8').match(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/i)[1]
function setup(saved, dark = false, blocked = false) {
  const storage = new Map(saved ? [['fridge-chef-theme', saved]] : [])
  const document = { documentElement: { dataset: {} }, querySelector: () => ({ setAttribute() {} }) }
  const events = {}
  const media = { matches: dark, addEventListener: (_, fn) => { events.media = fn } }
  const context = { document, window: { matchMedia: () => media, addEventListener: (name, fn) => { events[name] = fn } }, localStorage: {
    getItem: (key) => { if (blocked) throw Error('blocked'); return storage.get(key) },
    setItem: (key, val) => { if (blocked) throw Error('blocked'); storage.set(key, val) },
  }, matchMedia: () => media }
  runInNewContext(source + ';this.choose = setTheme;', context)
  return { context, media, events, storage, theme: () => document.documentElement.dataset.theme }
}
test('light is the default; saved dark is restored', () => {
  assert.equal(setup().theme(), 'light')
  assert.equal(setup('dark').theme(), 'dark')
  assert.equal(setup('invalid').theme(), 'light')
})
test('explicit choices persist and ignore OS changes', () => {
  const app = setup()
  app.context.choose('dark')
  assert.equal(app.storage.get('fridge-chef-theme'), 'dark')
  app.media.matches = false; app.events.media()
  assert.equal(app.theme(), 'dark')
})
test('system choice follows live OS changes', () => {
  const app = setup('system', false)
  app.media.matches = true; app.events.media()
  assert.equal(app.theme(), 'dark')
  app.media.matches = false; app.events.media()
  assert.equal(app.theme(), 'light')
})
test('storage changes synchronize tabs; unavailable storage is harmless', () => {
  const app = setup()
  app.events.storage({ key: 'fridge-chef-theme', newValue: 'dark' })
  assert.equal(app.theme(), 'dark')
  app.events.storage({ key: null, newValue: null })
  assert.equal(app.theme(), 'light')
  const blocked = setup(null, false, true)
  blocked.context.choose('dark')
  assert.equal(blocked.theme(), 'dark')
})
test('first-paint bootstrap agrees with runtime theme resolution', () => {
  for (const preference of [null, 'light', 'dark', 'system', 'invalid']) {
    for (const osDark of [true, false]) {
      const app = setup(preference, osDark)
      const expected = app.theme()
      app.context.document.documentElement.dataset.theme = ''
      runInNewContext(bootstrap, app.context)
      assert.equal(app.theme(), expected)
    }
  }
})
