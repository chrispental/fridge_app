import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { createQueryClient } from '../src/api/queries.js'
import { api } from '../src/api/client.js'
import ItemModal from '../src/components/ItemModal.jsx'
import MealCard from '../src/components/MealCard.jsx'
import { ToastProvider } from '../src/components/Toast.jsx'
import { localDatePlus } from '../src/utils/dates.js'
import { estimateExpiry } from '../src/utils/expiry.js'

vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ session: null }) }))

const wrap = (ui) => <QueryClientProvider client={createQueryClient()}><ToastProvider>{ui}</ToastProvider></QueryClientProvider>

it('estimates shelf life the same way as the backend table', () => {
  expect(estimateExpiry('dairy', 'fridge')).toBe(localDatePlus(10))
  expect(estimateExpiry('Fresh Produce', 'counter')).toBe(localDatePlus(7))
  expect(estimateExpiry('meat', 'freezer')).toBe(localDatePlus(90))
  expect(estimateExpiry('canned goods', 'pantry')).toBeNull()
})

it('prefills a new item\'s expiry from its category until the user picks a date', async () => {
  const user = userEvent.setup()
  render(wrap(<ItemModal item={{}} onClose={vi.fn()} />))
  const date = screen.getByLabelText(/Expires/)
  expect(date.value).toBe('')
  await user.type(screen.getByRole('combobox', { name: 'Category' }), 'dairy')
  expect(date.value).toBe(localDatePlus(10))
  expect(screen.getByText(/Estimated from the category/)).toBeTruthy()
  fireEvent.change(screen.getByRole('combobox', { name: 'Storage' }), { target: { value: 'freezer' } })
  expect(date.value).toBe(localDatePlus(90))
  // A manual date wins from then on.
  fireEvent.click(screen.getByRole('button', { name: '+3 days' }))
  expect(screen.queryByText(/Estimated from the category/)).toBeNull()
  fireEvent.change(screen.getByRole('combobox', { name: 'Storage' }), { target: { value: 'fridge' } })
  expect(date.value).toBe(localDatePlus(3))
})

it('does not touch the expiry of an existing item', async () => {
  const user = userEvent.setup()
  render(wrap(<ItemModal item={{ id: 3, name: 'milk', unit: 'cup', storage: 'fridge', expires_at: '2026-12-01' }} onClose={vi.fn()} />))
  await user.type(screen.getByRole('combobox', { name: 'Category' }), 'dairy')
  expect(screen.getByLabelText(/Expires/).value).toBe('2026-12-01')
})

it('can undo deleting an item from the toast', async () => {
  vi.spyOn(api, 'deleteItem').mockResolvedValue(null)
  const add = vi.spyOn(api, 'addItem').mockResolvedValue({ id: 9, name: 'milk' })
  const close = vi.fn()
  const item = { id: 3, name: 'milk', quantity: 2, unit: 'cup', storage: 'fridge', category: 'dairy', expires_at: '2026-12-01' }
  render(wrap(<ItemModal item={item} onClose={close} />))
  fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
  await waitFor(() => expect(close).toHaveBeenCalledOnce())
  fireEvent.click(await screen.findByRole('button', { name: 'Undo' }))
  await waitFor(() => expect(add).toHaveBeenCalledWith({
    name: 'milk', quantity: 2, unit: 'cup', storage: 'fridge', category: 'dairy', expires_at: '2026-12-01',
  }))
})

it('sends the leftovers choice when marking a meal cooked', async () => {
  const cook = vi.spyOn(api, 'cookMeal').mockResolvedValue({ id: 5, status: 'cooked' })
  const meal = { id: 5, title: 'Rice', status: 'suggested', recipe_json: { ingredients: [], steps: ['Cook.'] } }
  render(wrap(<MemoryRouter><MealCard meal={meal} /></MemoryRouter>))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Save leftovers to my fridge' }))
  fireEvent.click(screen.getByRole('button', { name: 'I cooked this' }))
  await waitFor(() => expect(cook).toHaveBeenCalledOnce())
  expect(cook.mock.calls[0][0]).toBe(5)
  expect(cook.mock.calls[0][3]).toBe(true)
  await screen.findByText(/Leftovers added to your fridge/)
})
