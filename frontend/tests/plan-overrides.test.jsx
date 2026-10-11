import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { api } from '../src/api/client.js'
import { createQueryClient } from '../src/api/queries.js'
import WeekPlanPage from '../src/pages/WeekPlanPage.jsx'
import { localDatePlus, planSlotLabel } from '../src/utils/dates.js'

vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ session: null }) }))

const notFound = () => Object.assign(new Error('No plan yet'), { status: 404 })

it('creates a plan with the chosen serving count and start date', async () => {
  vi.spyOn(api, 'getPreferences').mockResolvedValue({ household_size: 3 })
  vi.spyOn(api, 'getDeliveryStatus').mockResolvedValue({ used: false })
  vi.spyOn(api, 'getCurrentPlan').mockRejectedValue(notFound())
  const create = vi.spyOn(api, 'createPlan').mockResolvedValue({ id: 1, status: 'queued', requested_count: 5, servings: 6, start_date: '2026-10-12', entries: [] })
  const client = createQueryClient()
  render(<QueryClientProvider client={client}><MemoryRouter><WeekPlanPage /></MemoryRouter></QueryClientProvider>)
  await waitFor(() => expect(screen.getByRole('button', { name: 'Plan my week' }).disabled).toBe(false))
  expect(screen.getByLabelText('Starting').value).toBe(localDatePlus(0))
  expect(screen.getByRole('combobox', { name: 'Cooking for' }).value).toBe('3')
  fireEvent.change(screen.getByLabelText('How many meals?'), { target: { value: '5' } })
  fireEvent.change(screen.getByLabelText('Starting'), { target: { value: '2026-10-12' } })
  fireEvent.change(screen.getByRole('combobox', { name: 'Cooking for' }), { target: { value: '6' } })
  fireEvent.click(screen.getByRole('button', { name: 'Plan my week' }))
  await waitFor(() => expect(create).toHaveBeenCalledOnce())
  expect(create.mock.calls[0][0]).toMatchObject({ count: 5, servings: 6, startDate: '2026-10-12' })
  await screen.findByText(/from Mon, Oct 12 · serves 6/)
  client.clear()
})

it('labels each slot with its date when the plan has one', () => {
  expect(planSlotLabel('2026-10-12', 0)).toBe('Day 1 · Mon, Oct 12')
  expect(planSlotLabel('2026-10-12', 2)).toBe('Day 3 · Wed, Oct 14')
  expect(planSlotLabel(null, 2)).toBe('Day 3')
})
