import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { api } from '../src/api/client.js'
import { createQueryClient } from '../src/api/queries.js'
import SuggestMeal from '../src/pages/SuggestMeal.jsx'

vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ session: null }) }))

it('refreshes a generated batch after cooking without losing its order or cooked card', async () => {
  let cooked = false
  const makeMeal = (id) => ({ id, title: `Rice ${id}`, status: cooked && id === 1 ? 'cooked' : 'suggested',
    recipe_json: { ingredients: [{ name: 'milk', quantity: 1, unit: 'cup',
      in_stock: !cooked, stock_status: cooked ? 'missing' : 'have' }], steps: [] } })
  vi.spyOn(api, 'getPreferences').mockResolvedValue({ household_size: 2 })
  vi.spyOn(api, 'getDeliveryStatus').mockResolvedValue({ used: false })
  vi.spyOn(api, 'getMeals').mockImplementation(async () => cooked ? [makeMeal(2)] : [])
  vi.spyOn(api, 'suggestMeals').mockImplementation(async () => [makeMeal(1), makeMeal(2)])
  vi.spyOn(api, 'getMeal').mockImplementation(async (id) => makeMeal(id))
  vi.spyOn(api, 'cookMeal').mockImplementation(async () => { cooked = true; return makeMeal(1) })
  const client = createQueryClient()
  const view = render(<QueryClientProvider client={client}><MemoryRouter><SuggestMeal /></MemoryRouter></QueryClientProvider>)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Surprise me' }).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: 'Surprise me' }))
  await screen.findByRole('heading', { name: 'Rice 1' })
  fireEvent.click(screen.getAllByRole('button', { name: 'I cooked this' })[0])
  await waitFor(() => expect(screen.getAllByText('+ milk (1 cup)')).toHaveLength(2))
  expect(screen.getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['Rice 1', 'Rice 2'])
  const firstCard = screen.getByRole('heading', { name: 'Rice 1' }).closest('.meal-card')
  expect(within(firstCard).getByText('Cooked')).toBeTruthy()
  view.unmount()
  client.clear()
})
