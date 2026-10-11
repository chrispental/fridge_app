import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { api } from '../src/api/client.js'
import { createQueryClient } from '../src/api/queries.js'
import MealCard from '../src/components/MealCard.jsx'
import InsightsPage from '../src/pages/InsightsPage.jsx'

vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ session: null }) }))

const base = { id: 3, title: 'Dal', status: 'suggested', recipe_json: { ingredients: [{ name: 'lentils', quantity: 1, unit: 'cup', in_stock: true }], steps: ['Simmer.'] } }
const mount = (ui) => {
  const client = createQueryClient()
  return { client, ...render(<QueryClientProvider client={client}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>) }
}

it('shows approximate per-serving nutrition and its origin', () => {
  const { client } = mount(<MealCard meal={{ ...base, recipe_json: { ...base.recipe_json, nutrition: { calories: 320, protein_g: 18.4, carbs_g: 50, fat_g: 4, source: 'recipe' } } }} />)
  expect(screen.getByText(/≈ 320 kcal · 18 g protein · 50 g carbs · 4 g fat/)).toBeTruthy()
  expect(screen.getByText(/per serving · from the recipe/)).toBeTruthy()
  client.clear()
})

it('offers a one-tap estimate when a recipe has none', async () => {
  const estimate = vi.spyOn(api, 'estimateNutrition').mockResolvedValue({ ...base, recipe_json: { ...base.recipe_json, nutrition: { calories: 210, protein_g: 12, carbs_g: 30, fat_g: 3, source: 'estimate' } } })
  const { client } = mount(<MealCard meal={base} />)
  fireEvent.click(screen.getByRole('button', { name: 'Estimate nutrition' }))
  await waitFor(() => expect(estimate).toHaveBeenCalledWith(3))
  client.clear()
})

it('summarises average nutrition in Insights when estimates exist', async () => {
  vi.spyOn(api, 'getMealStats').mockResolvedValue({
    totals: { total: 2, suggested: 0, cooked: 2, ordered: 0 }, top_rated: [], cuisines: [], cooks_per_week: [], top_ingredients: [], feedback_tags: [],
    nutrition: { meals: 2, calories: 500, protein_g: 25, carbs_g: 50, fat_g: 15 },
  })
  const { client } = mount(<InsightsPage />)
  await screen.findByText('Per serving, on average')
  expect(screen.getByText('500')).toBeTruthy()
  expect(screen.getByText(/25 g protein · 50 g carbs · 15 g fat/)).toBeTruthy()
  client.clear()
})
