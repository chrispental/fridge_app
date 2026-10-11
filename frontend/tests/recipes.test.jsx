import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { api } from '../src/api/client.js'
import { createQueryClient } from '../src/api/queries.js'
import RecipesPage from '../src/pages/RecipesPage.jsx'
import MealCard from '../src/components/MealCard.jsx'
import { ToastProvider } from '../src/components/Toast.jsx'

vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ session: null }) }))

const savedMeal = { id: 7, title: 'Lemon Chicken', status: 'saved', favorite: false,
  recipe_json: { ingredients: [{ name: 'chicken', quantity: 1, unit: 'lb', in_stock: false, stock_status: 'missing' }], steps: ['Roast.'],
    source: { title: 'Lemon Chicken', url: 'https://example.com/lemon' } } }

const wrap = (ui) => {
  const client = createQueryClient()
  return { client, ...render(<QueryClientProvider client={client}><ToastProvider><MemoryRouter>{ui}</MemoryRouter></ToastProvider></QueryClientProvider>) }
}

it('imports a recipe from a web address into the book', async () => {
  let book = []
  vi.spyOn(api, 'getDeliveryStatus').mockResolvedValue({ used: false })
  vi.spyOn(api, 'getRecipes').mockImplementation(async () => book)
  const importRecipe = vi.spyOn(api, 'importRecipe').mockImplementation(async () => { book = [savedMeal]; return savedMeal })
  const { client } = wrap(<RecipesPage />)
  await screen.findByText('Your recipe book is empty')
  expect(screen.getByRole('button', { name: 'Save recipe' }).disabled).toBe(true)
  fireEvent.change(screen.getByRole('textbox', { name: 'Recipe web address' }), { target: { value: 'https://example.com/lemon' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save recipe' }))
  await screen.findByRole('heading', { name: 'Lemon Chicken' })
  expect(importRecipe).toHaveBeenCalledWith({ url: 'https://example.com/lemon' })
  const card = screen.getByRole('heading', { name: 'Lemon Chicken' }).closest('.meal-card')
  expect(within(card).getByRole('button', { name: 'Add to this week' })).toBeTruthy()
  expect(within(card).queryByRole('button', { name: 'Order delivery' })).toBeNull()
  expect(screen.getByRole('textbox', { name: 'Recipe web address' }).value).toBe('')
  client.clear()
})

it('shows an inline error when the import fails and switches to pasted text', async () => {
  vi.spyOn(api, 'getDeliveryStatus').mockResolvedValue({ used: false })
  vi.spyOn(api, 'getRecipes').mockResolvedValue([])
  const importRecipe = vi.spyOn(api, 'importRecipe').mockRejectedValueOnce(new Error("That page doesn't seem to contain a recipe."))
  const { client } = wrap(<RecipesPage />)
  fireEvent.click(screen.getByRole('button', { name: 'Paste a recipe' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Recipe text' }), { target: { value: 'Lemon chicken: roast chicken with lemon for an hour.' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save recipe' }))
  await screen.findByRole('alert')
  expect(importRecipe.mock.calls[0][0]).toEqual({ text: 'Lemon chicken: roast chicken with lemon for an hour.' })
  client.clear()
})

it('toggles favourite from the card', async () => {
  const setFavorite = vi.spyOn(api, 'setFavorite').mockResolvedValue({ ...savedMeal, favorite: true })
  const { client } = wrap(<MealCard meal={savedMeal} />)
  fireEvent.click(screen.getByRole('button', { name: 'Add to favourites' }))
  await waitFor(() => expect(setFavorite).toHaveBeenCalledWith(7, true))
  client.clear()
})

it('cooking a saved recipe logs a copy and leaves the card in the book', async () => {
  const cook = vi.spyOn(api, 'cookMeal').mockResolvedValue({ id: 99, title: 'Lemon Chicken', status: 'cooked' })
  const { client } = wrap(<MealCard meal={savedMeal} />)
  fireEvent.click(screen.getByRole('button', { name: 'I cooked this' }))
  await screen.findByText('Logged Lemon Chicken to your history')
  expect(cook).toHaveBeenCalledOnce()
  expect(screen.getByRole('button', { name: 'I cooked this' })).toBeTruthy()
  expect(screen.queryByText('Cooked')).toBeNull()
  client.clear()
})
