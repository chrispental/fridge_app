import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { formatQty } from '../src/utils/quantity.js'
import CookingProvider from '../src/components/CookingProvider.jsx'
import CookMode from '../src/components/CookMode.jsx'
import SuggestMeal from '../src/pages/SuggestMeal.jsx'
import MealCard from '../src/components/MealCard.jsx'

vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ session: null }) }))
const { order } = vi.hoisted(() => ({ order: vi.fn() }))
vi.mock('../src/api/queries.js', () => ({
  usePreferences: () => ({ data: { household_size: 2 } }),
  useDeliveryStatus: () => ({ data: { used: false } }),
  useMeals: () => ({ data: [] }),
  useSuggestMeals: () => ({ mutate: vi.fn() }),
  useCookMeal: () => ({}), useSubmitFeedback: () => ({}),
  useOrderDelivery: () => ({ mutate: order }), useImportMealToList: () => ({}),
}))

const meal = { id: 41, title: 'Rice bowl', recipe_json: { ingredients: [], steps: ['Simmer for 1 minute.'] } }

it('shows at most two decimals for quantities', () => {
  expect(formatQty(10 / 12)).toBe('0.83')
  expect(formatQty(1.25)).toBe('1.25')
  expect(formatQty(2)).toBe('2')
})

it('ignores cook progress and timers saved for a different recipe with the same id', () => {
  localStorage.setItem('fridge:local:cook:41', JSON.stringify({ index: 1, checked: [], requestId: 'old', complete: false, meal: 'Lasagna|6' }))
  localStorage.setItem('fridge:local:timers:all', JSON.stringify({
    'fridge:local:cook:41:timers:s0-0': { seconds: 900, label: '15 min', remaining: 340, running: false, done: false, endTime: 0 },
  }))
  render(<CookingProvider><CookMode meal={meal} onClose={() => {}} onCook={vi.fn()} /></CookingProvider>)
  expect(screen.getByText('Mise en place')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.getByText('1:00')).toBeTruthy()
  expect(screen.queryByText('5:40')).toBeNull()
})

it('asks before using the weekly delivery night', () => {
  render(<MealCard meal={meal} deliveryAvailable />)
  fireEvent.click(screen.getByRole('button', { name: /Order delivery/ }))
  expect(order).not.toHaveBeenCalled()
  expect(screen.getByText(/place the order yourself/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
  fireEvent.click(screen.getByRole('button', { name: /Order delivery/ }))
  fireEvent.click(screen.getByRole('button', { name: /Use delivery night/ }))
  expect(order).toHaveBeenCalledWith(41, expect.anything())
})

it('does not blame the fridge before any suggestion was requested', () => {
  render(<MemoryRouter><SuggestMeal /></MemoryRouter>)
  expect(screen.getByText('No ideas yet')).toBeTruthy()
  expect(screen.queryByText('No suggestions')).toBeNull()
})

it('judges low stock by unit', async () => {
  const { isLowStock } = await import('../src/utils/quantity.js')
  expect(isLowStock({ quantity: 1, unit: 'piece' })).toBe(true)
  expect(isLowStock({ quantity: 1, unit: 'gallon' })).toBe(false)
  expect(isLowStock({ quantity: 0.5, unit: 'dozen' })).toBe(true)
  expect(isLowStock({ quantity: 1, unit: 'unknown' })).toBe(false)
  expect(isLowStock({ quantity: null, unit: 'jar' })).toBe(false)
})

it('pluralises spelled-out units and leaves abbreviations alone', async () => {
  const { formatAmount } = await import('../src/utils/quantity.js')
  expect(formatAmount(2, 'piece')).toBe('2 pieces')
  expect(formatAmount(1, 'piece')).toBe('1 piece')
  expect(formatAmount(0.5, 'bunch')).toBe('0.5 bunches')
  expect(formatAmount(10 / 12, 'dozen')).toBe('0.83 dozen')
  expect(formatAmount(2, 'lb')).toBe('2 lb')
  expect(formatAmount(3, 'unknown')).toBe('3')
})

it('matches category icons regardless of plural or case', async () => {
  const { default: ItemTile } = await import('../src/components/ItemTile.jsx')
  const icon = (category) => render(<ItemTile item={{ name: 'x', quantity: 2, unit: 'lb', category }} onEdit={() => {}} />)
    .container.querySelector('.tile-photo svg').getAttribute('class')
  expect(icon('Grains')).toBe(icon('grain'))
  expect(icon('Vegetables')).toBe(icon('produce'))
  expect(icon('Grains')).not.toBe(icon('spreads'))
})
