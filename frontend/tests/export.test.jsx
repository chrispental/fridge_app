import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { api } from '../src/api/client.js'
import { createQueryClient } from '../src/api/queries.js'
import PreferencesPage from '../src/pages/PreferencesPage.jsx'
import { ToastProvider } from '../src/components/Toast.jsx'

it('downloads the kitchen as a dated JSON file from Settings', async () => {
  vi.spyOn(api, 'getPreferences').mockResolvedValue({ name: 'Chris', household_size: 2, allergies: [], dietary_restrictions: [], equipment: [], max_complexity: 3, disliked_ingredients: [], disliked_cuisines: [], no_repeat_days: 14, location: '', pantry_staples: [] })
  const blob = new Blob(['{"format":"fridge-chef-export/1"}'], { type: 'application/json' })
  const exportData = vi.spyOn(api, 'exportData').mockResolvedValue(blob)
  const clicks = []
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () { clicks.push(this.download) })
  const client = createQueryClient()
  render(<QueryClientProvider client={client}><ToastProvider><PreferencesPage /></ToastProvider></QueryClientProvider>)
  fireEvent.click(await screen.findByRole('button', { name: 'Download my data' }))
  await waitFor(() => expect(clicks).toHaveLength(1))
  expect(exportData).toHaveBeenCalledOnce()
  expect(clicks[0]).toMatch(/^fridge-chef-export-\d{4}-\d{2}-\d{2}\.json$/)
  await screen.findByText('Your kitchen data is downloading')
  click.mockRestore()
  client.clear()
})
