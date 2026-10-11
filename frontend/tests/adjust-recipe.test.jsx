import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { api } from '../src/api/client.js'
import { createQueryClient } from '../src/api/queries.js'
import SuggestMeal from '../src/pages/SuggestMeal.jsx'
import MealCard from '../src/components/MealCard.jsx'

vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ session: null }) }))

const original = { id: 7, title: 'Chicken Curry', status: 'suggested',
  recipe_json: { ingredients: [{ name: 'chicken', quantity: 1, unit: 'lb', in_stock: true, stock_status: 'have' }], steps: ['Cook.'] } }
const adjusted = { ...original, title: 'Chickpea Curry',
  recipe_json: { ...original.recipe_json, adjustments: ['Vegetarian'],
    ingredients: [{ name: 'chickpeas', quantity: 1, unit: 'can', in_stock: false, stock_status: 'missing' }] } }

it('rewrites a suggested recipe in place from a one-tap chip', async () => {
  vi.spyOn(api, 'getPreferences').mockResolvedValue({ household_size: 2 })
  vi.spyOn(api, 'getDeliveryStatus').mockResolvedValue({ used: false })
  vi.spyOn(api, 'getMeals').mockResolvedValue([])
  vi.spyOn(api, 'suggestMeals').mockResolvedValue([original])
  vi.spyOn(api, 'getMeal').mockResolvedValue(original)
  const adjust = vi.spyOn(api, 'adjustMeal').mockResolvedValue(adjusted)
  const client = createQueryClient()
  const view = render(<QueryClientProvider client={client}><MemoryRouter><SuggestMeal /></MemoryRouter></QueryClientProvider>)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Surprise me' }).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: 'Surprise me' }))
  await screen.findByRole('heading', { name: 'Chicken Curry' })

  fireEvent.click(screen.getByRole('button', { name: 'Adjust recipe' }))
  fireEvent.click(screen.getByRole('button', { name: 'Vegetarian' }))
  await screen.findByRole('heading', { name: 'Chickpea Curry' })
  expect(adjust).toHaveBeenCalledWith(7, 'Vegetarian')
  expect(screen.getByText(/Adjusted: Vegetarian/)).toBeTruthy()
  expect(screen.getByText('+ chickpeas (1 can)')).toBeTruthy()
  expect(screen.queryByRole('group', { name: 'Adjust this recipe' })).toBeNull()
  view.unmount()
  client.clear()
})

it('sends free-text instructions and keeps the panel open on failure', async () => {
  const adjust = vi.spyOn(api, 'adjustMeal').mockRejectedValueOnce(new Error('That adjustment would add an ingredient you\'re allergic to, so it was not applied.'))
  const client = createQueryClient()
  render(<QueryClientProvider client={client}><MemoryRouter><MealCard meal={original} /></MemoryRouter></QueryClientProvider>)
  fireEvent.click(screen.getByRole('button', { name: 'Adjust recipe' }))
  const input = screen.getByRole('textbox', { name: 'Describe the change' })
  expect(screen.getByRole('button', { name: 'Apply' }).disabled).toBe(true)
  fireEvent.change(input, { target: { value: '  add peanuts ' } })
  fireEvent.click(screen.getByRole('button', { name: 'Apply' }))
  await screen.findByRole('alert')
  expect(adjust).toHaveBeenCalledWith(7, 'add peanuts')
  expect(screen.getByRole('group', { name: 'Adjust this recipe' })).toBeTruthy()
  client.clear()
})

it('offers no adjustment once a meal is cooked', () => {
  const client = createQueryClient()
  render(<QueryClientProvider client={client}><MemoryRouter><MealCard meal={{ ...original, status: 'cooked' }} /></MemoryRouter></QueryClientProvider>)
  expect(screen.queryByRole('button', { name: 'Adjust recipe' })).toBeNull()
  client.clear()
})
