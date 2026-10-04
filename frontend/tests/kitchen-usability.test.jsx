import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { api } from '../src/api/client.js'
import { createQueryClient } from '../src/api/queries.js'
import InventoryPage from '../src/pages/InventoryPage.jsx'
import ShoppingListPage from '../src/pages/ShoppingListPage.jsx'
import ResumeCooking from '../src/components/ResumeCooking.jsx'
import CookingProvider from '../src/components/CookingProvider.jsx'
import MealCard from '../src/components/MealCard.jsx'

const auth = vi.hoisted(() => ({ session: null }))
vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => auth }))

function mount(element) {
  const client = createQueryClient()
  client.setDefaultOptions({ queries: { retry: false } })
  const view = render(<QueryClientProvider client={client}><MemoryRouter><CookingProvider>{element}</CookingProvider></MemoryRouter></QueryClientProvider>)
  return { ...view, stop: () => { view.unmount(); client.clear() } }
}

it('keeps a zero-match storage filter visible and offers search across all locations', async () => {
  vi.spyOn(api, 'getInventory').mockResolvedValue([
    { id: 1, name: 'milk', quantity: 1, unit: 'gallon', storage: 'fridge' },
    { id: 2, name: 'rice', quantity: 2, unit: 'lb', storage: 'pantry' },
  ])
  const view = mount(<InventoryPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Pantry (1)' }))
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'milk' } })
  expect(screen.getByRole('button', { name: 'Pantry (0)' })).toBeTruthy()
  expect(screen.getByText('No matches')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Search all locations' }))
  expect(screen.getByText('milk')).toBeTruthy()
  expect(screen.getByRole('searchbox').value).toBe('milk')
  view.stop()
})

it('keeps shopping edits on failure and moves the purchased quantity after retry', async () => {
  let item = { id: 9, name: 'butter', quantity: 1, unit: 'tbsp', source: 'meal', checked: true }
  vi.spyOn(api, 'getShoppingListItems').mockImplementation(async () => [item])
  const update = vi.spyOn(api, 'updateShoppingItem').mockRejectedValueOnce(new Error('Try again'))
    .mockImplementation(async (_id, body) => { item = { ...item, ...body }; return item })
  const move = vi.spyOn(api, 'checkedToInventory').mockImplementation(async () => [{ ...item }])
  const view = mount(<ShoppingListPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Edit butter' }))
  let dialog = screen.getByRole('dialog')
  fireEvent.change(within(dialog).getByLabelText('Quantity'), { target: { value: '1' } })
  fireEvent.change(within(dialog).getByLabelText('Unit'), { target: { value: 'lb' } })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
  await within(dialog).findByRole('alert')
  expect(within(dialog).getByLabelText('Unit').value).toBe('lb')
  fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(update).toHaveBeenLastCalledWith(9, { name: 'butter', quantity: 1, unit: 'lb' })
  expect(item.checked).toBe(true)
  expect(item.source).toBe('meal')
  fireEvent.click(screen.getByRole('button', { name: 'Add 1 to my fridge' }))
  await waitFor(() => expect(move).toHaveBeenCalledOnce())
  view.stop()
})

it('keeps a blank shopping quantity unknown', async () => {
  const item = { id: 9, name: 'butter', quantity: 1, unit: 'tbsp', source: 'meal', checked: false }
  vi.spyOn(api, 'getShoppingListItems').mockResolvedValue([item])
  const update = vi.spyOn(api, 'updateShoppingItem').mockResolvedValue({ ...item, quantity: null })
  const view = mount(<ShoppingListPage />)
  fireEvent.click(await screen.findByRole('button', { name: 'Edit butter' }))
  const dialog = screen.getByRole('dialog')
  fireEvent.change(within(dialog).getByLabelText('Quantity'), { target: { value: '' } })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(update).toHaveBeenCalledWith(9, { name: 'butter', quantity: null, unit: 'tbsp' }))
  view.stop()
})

const meal = { id: 42, title: 'Rice', status: 'suggested', recipe_json: { ingredients: [], steps: ['Simmer for 1 minute.'] } }
it('resumes directly after remount, preserves progress when dismissed, and clears completed reminders', async () => {
  vi.spyOn(api, 'getMeal').mockResolvedValue(meal)
  vi.spyOn(api, 'cookMeal').mockResolvedValue({ ...meal, status: 'cooked' })
  let view = mount(<><ResumeCooking /><MealCard meal={meal} /></>)
  fireEvent.click(screen.getByRole('button', { name: 'Begin cooking' }))
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  fireEvent.click(screen.getByRole('button', { name: 'Start timer' }))
  fireEvent.click(screen.getByRole('button', { name: 'Close cook mode' }))
  expect(screen.getByRole('button', { name: 'Resume cooking', exact: true })).toBeTruthy()
  view.stop()
  view = mount(<><ResumeCooking /><MealCard meal={meal} /></>)
  fireEvent.click(await screen.findByRole('button', { name: 'Resume cooking: Rice' }))
  expect(screen.getByText('Step 1 of 1')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Pause' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Close cook mode' }))
  fireEvent.click(screen.getByRole('button', { name: 'Dismiss cooking reminder' }))
  expect(screen.queryByRole('button', { name: 'Resume cooking: Rice' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Resume cooking', exact: true }))
  expect(screen.getByText('Step 1 of 1')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Finish' }))
  fireEvent.click(screen.getByRole('button', { name: 'Mark as cooked' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Done' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(screen.queryByRole('button', { name: 'Resume cooking: Rice' })).toBeNull()
  view.stop()
})

it('ignores reminders belonging to another account or a replaced recipe', async () => {
  localStorage.setItem('fridge:someone-else:cook:active', JSON.stringify({ id: 42 }))
  const getMeal = vi.spyOn(api, 'getMeal').mockResolvedValue(meal)
  let view = mount(<ResumeCooking />)
  expect(getMeal).not.toHaveBeenCalled()
  view.stop()
  localStorage.setItem('fridge:local:cook:active', JSON.stringify({ id: 42 }))
  localStorage.setItem('fridge:local:cook:42', JSON.stringify({ index: 1, meal: 'Old dish|7' }))
  view = mount(<ResumeCooking />)
  await waitFor(() => expect(getMeal).toHaveBeenCalledWith(42))
  expect(screen.queryByRole('button', { name: /Resume cooking/ })).toBeNull()
  view.stop()
})
