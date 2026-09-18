import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { stepSafety } from '../src/utils/stepSafety.js'
import CookingProvider from '../src/components/CookingProvider.jsx'
import CookMode from '../src/components/CookMode.jsx'
import SuggestMeal from '../src/pages/SuggestMeal.jsx'
import MealCard from '../src/components/MealCard.jsx'

vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ session: null }) }))
const { mutate } = vi.hoisted(() => ({ mutate: vi.fn() }))
vi.mock('../src/api/queries.js', () => ({
  usePreferences: () => ({ data: { household_size: 3 } }),
  useDeliveryStatus: () => ({ data: { used: false } }),
  useMeals: () => ({ data: [] }),
  useSuggestMeals: () => ({ mutate }),
  useCookMeal: () => ({}), useSubmitFeedback: () => ({}),
  useOrderDelivery: () => ({}), useImportMealToList: () => ({}),
}))

const meal = { id: 72, title: 'Roasted carrots', recipe_json: {
  servings: 3, image_url: 'https://example.com/unrelated.jpg', ingredients: [],
  steps: ['Roast carrots in a pan in the oven.', 'Remove the hot pan from the oven.'],
} }

it('warns about hot cookware, retained heat, steam, and oil at relevant steps', () => {
  expect(stepSafety(meal.recipe_json.steps, 0)).toEqual([])
  expect(stepSafety(meal.recipe_json.steps, 1).join(' ')).toContain('handles stay hot')
  expect(stepSafety(['Drain the boiling pasta.'], 0).join(' ')).toContain('steam')
  expect(stepSafety(['Fry in hot oil.'], 0).join(' ')).toContain('splashes')
  expect(stepSafety(['Heat oil in a skillet. Add the carrots and cook for 5 minutes.'], 0).join(' ')).toContain('splashes')
  expect(stepSafety(['Chop lettuce.', 'Mix with dressing.'], 1)).toEqual([])
  expect(stepSafety(['Whisk olive oil, parsley, salt, and a few dashes of hot sauce in a small bowl.'], 0)).toEqual([])
  expect(stepSafety(['Put the baking sheet in the oven.', 'Roast for 25 minutes, flipping the carrots halfway through.'], 1).join(' ')).toContain('dry oven mitts')
  expect(stepSafety(['Preheat the oven and place the baking sheet inside.', 'Roast for 25 minutes, flipping the carrots halfway through.'], 1).join(' ')).toContain('dry oven mitts')
})


it('does not repeat precautions already in the instruction or warn on routine heating', () => {
  for (const step of [
    'Preheat the oven to 425°F.',
    'Bring rice to a boil, then cover and simmer for 18 minutes.',
    'Use dry oven mitts to remove the hot baking tray from the oven.',
    'Lower food gently into hot oil and fry for 5 minutes.',
    'Open the lid away from your face to release steam.',
    'Drain the boiling pasta slowly away from your body.',
    'Remove the pan from the heat and let it rest.',
  ]) expect(stepSafety([step], 0)).toEqual([])
  expect(stepSafety(['Drain boiling water and remove the hot pot.'], 0)).toHaveLength(1)
})

it('shows servings and a safety reminder before the cooking action', () => {
  render(<CookingProvider><CookMode meal={meal} onClose={vi.fn()} onCook={vi.fn()} /></CookingProvider>)
  expect(screen.getByText('Ingredients for 3 people.')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.queryByLabelText('Cooking safety')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  expect(screen.getByLabelText('Cooking safety').textContent).toContain('handles stay hot')
})

it('includes safety reminders in expanded recipes and ignores old search photos', () => {
  render(<MealCard meal={meal} />)
  fireEvent.click(screen.getByRole('button', { name: 'Show instructions' }))
  expect(screen.getAllByLabelText('Cooking safety')).toHaveLength(1)
  expect(screen.queryByRole('img')).toBeNull()
})

it('defaults to household size and sends the chosen servings for a surprise meal', () => {
  render(<MemoryRouter><SuggestMeal /></MemoryRouter>)
  expect(screen.getByLabelText('Cooking for').value).toBe('3')
  fireEvent.change(screen.getByLabelText('Cooking for'), { target: { value: '5' } })
  fireEvent.click(screen.getByRole('button', { name: 'Surprise me' }))
  expect(mutate).toHaveBeenLastCalledWith({ count: 5, idea: null, servings: 5 })
})

it('preserves the serving choice on an automatic request from Home', () => {
  render(<MemoryRouter initialEntries={[{ pathname: '/cook', state: { run: true, idea: 'Soup', servings: 6 } }]}><SuggestMeal /></MemoryRouter>)
  expect(mutate).toHaveBeenLastCalledWith({ count: 5, idea: 'Soup', servings: 6 })
  expect(screen.getByLabelText('Cooking for').value).toBe('6')
})
