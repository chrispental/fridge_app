import { it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
const state = vi.hoisted(() => ({ status: 'pending_review', mutate: vi.fn() }))
vi.mock('../src/api/queries.js', () => ({
  useExtraction: () => ({ data: { status: state.status, items: [{ name: 'apples', quantity: 3, unit: 'piece', confidence: 1 }] } }),
  useConfirmExtraction: () => ({ mutate: state.mutate }),
}))
vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ session: { user: { id: 'test-user' } } }) }))
import { api } from '../src/api/client.js'
import ReviewExtraction from '../src/pages/ReviewExtraction.jsx'
const page = () => <MemoryRouter initialEntries={['/review/7']}><Routes><Route path="/review/:batchId" element={<ReviewExtraction />} /></Routes></MemoryRouter>

it('restores edits after remount and retrieves the photo through the authenticated API', async () => {
  state.status = 'pending_review'
  const photo = vi.spyOn(api, 'getExtractionImage').mockResolvedValue(new Blob(['photo']))
  const user = userEvent.setup()
  const view = render(page())
  await user.clear(screen.getByLabelText('Quantity for apples'))
  await user.type(screen.getByLabelText('Quantity for apples'), '6')
  view.unmount()
  render(page())
  expect(screen.getByLabelText('Quantity for apples').value).toBe('6')
  await waitFor(() => expect(screen.getByAltText('Original grocery photo for comparison')).toBeTruthy())
  expect(photo).toHaveBeenCalledWith('7', expect.any(AbortSignal))
})

it('does not offer to add a confirmed scan again', () => {
  state.status = 'confirmed'
  vi.spyOn(api, 'getExtractionImage').mockResolvedValue(new Blob())
  render(page())
  expect(screen.getByText('This scan is already saved')).toBeTruthy()
  expect(screen.queryByRole('button', { name: /to inventory/ })).toBeNull()
})
