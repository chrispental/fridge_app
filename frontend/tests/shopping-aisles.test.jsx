import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { api } from '../src/api/client.js'
import { createQueryClient } from '../src/api/queries.js'
import ShoppingListPage from '../src/pages/ShoppingListPage.jsx'
import { groupByAisle } from '../src/utils/aisles.js'

const rows = [
  { id: 1, name: 'soy sauce', unit: 'tbsp', quantity: 2, checked: false, source: 'meal', category: 'condiment' },
  { id: 2, name: 'lemons', unit: 'piece', quantity: 3, checked: false, source: 'manual', category: 'produce' },
  { id: 3, name: 'gruyère', unit: 'oz', quantity: 8, checked: false, source: 'plan', category: 'dairy' },
  { id: 4, name: 'bell pepper', unit: 'piece', quantity: 1, checked: false, source: 'plan', category: 'produce' },
  { id: 5, name: 'flour', unit: 'lb', quantity: 1, checked: true, source: 'manual', category: 'pantry' },
  { id: 6, name: 'legacy thing', unit: 'unknown', quantity: null, checked: false, source: 'manual', category: null },
]

const mount = (ui) => {
  const client = createQueryClient()
  return { client, ...render(<QueryClientProvider client={client}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>) }
}

it('groups rows into aisles in store order and drops empty sections', () => {
  const groups = groupByAisle(rows.filter((r) => !r.checked))
  expect(groups.map((g) => [g.value, g.items.map((i) => i.name)])).toEqual([
    ['produce', ['lemons', 'bell pepper']],
    ['dairy', ['gruyère']],
    ['condiment', ['soy sauce']],
    ['other', ['legacy thing']],
  ])
})

it('walks the list aisle by aisle and searches across sections', async () => {
  vi.spyOn(api, 'getShoppingListItems').mockResolvedValue(rows)
  const { client } = mount(<ShoppingListPage />)
  await screen.findByText('To buy (5)')
  const headings = screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent)
  expect(headings).toEqual(['🥕Produce2', '🧀Dairy & eggs1', '🫙Condiments1', '🛒Other1'])
  expect(within(screen.getByRole('region', { name: 'Produce' })).getByText('lemons')).toBeTruthy()
  expect(screen.getByText('In your cart (1)')).toBeTruthy()

  fireEvent.change(screen.getByRole('searchbox', { name: 'Search shopping list' }), { target: { value: 'gru' } })
  expect(screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent)).toEqual(['🧀Dairy & eggs1'])
  expect(screen.queryByText('lemons')).toBeNull()
  expect(screen.getByText(/Nothing in your cart matches/)).toBeTruthy()
  client.clear()
})

it('lets the edit dialog move a row to another aisle', async () => {
  vi.spyOn(api, 'getShoppingListItems').mockResolvedValue([rows[0]])
  const update = vi.spyOn(api, 'updateShoppingItem').mockResolvedValue({ ...rows[0], category: 'pantry' })
  const { client } = mount(<ShoppingListPage />)
  await screen.findByText('soy sauce')
  fireEvent.click(screen.getByRole('button', { name: 'Edit soy sauce' }))
  const aisle = screen.getByRole('combobox', { name: 'Aisle' })
  expect(aisle.value).toBe('condiment')
  fireEvent.change(aisle, { target: { value: 'pantry' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save' }))
  await waitFor(() => expect(update).toHaveBeenCalledOnce())
  expect(update.mock.calls[0][1]).toMatchObject({ name: 'soy sauce', category: 'pantry' })
  client.clear()
})
