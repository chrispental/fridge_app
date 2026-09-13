import { it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
vi.mock('../src/api/client.js', () => ({ api: { getShoppingList: vi.fn() } }))
import { api } from '../src/api/client.js'
import { usePlanShoppingList } from '../src/api/queries.js'

it('refreshes quantities as a background plan adds meals', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30000 } } })
  api.getShoppingList.mockResolvedValueOnce({ to_buy: [] }).mockResolvedValueOnce({ to_buy: [{ name: 'rice', quantity: 3 }] })
  const wrapper = ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  const { result, rerender } = renderHook((plan) => usePlanShoppingList(plan), { wrapper, initialProps: { id: 1, entries: [] } })
  await waitFor(() => expect(result.current.data).toEqual({ to_buy: [] }))
  rerender({ id: 1, entries: [{ meal: { id: 42 } }] })
  await waitFor(() => expect(result.current.data.to_buy).toHaveLength(1))
  expect(api.getShoppingList).toHaveBeenCalledTimes(2)
  client.clear()
})
