import { it, expect, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { createQueryClient } from '../src/api/queries.js'
import { api } from '../src/api/client.js'
import ItemModal from '../src/components/ItemModal.jsx'

it('preserves input after a failed save and closes only after a successful retry', async () => {
  const add = vi.spyOn(api, 'addItem').mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValueOnce({ id: 8, name: 'carrots' })
  const close = vi.fn()
  const user = userEvent.setup()
  render(<QueryClientProvider client={createQueryClient()}><ItemModal item={{}} onClose={close} /></QueryClientProvider>)
  await user.type(screen.getByRole('textbox', { name: 'Name' }), 'carrots')
  await user.click(screen.getByRole('button', { name: 'Add', exact: true }))
  await screen.findByRole('alert')
  expect(screen.getByRole('textbox', { name: 'Name' }).value).toBe('carrots')
  expect(close).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: 'Add', exact: true }))
  await waitFor(() => expect(close).toHaveBeenCalledOnce())
  expect(add).toHaveBeenCalledTimes(2)
})

it('uses a named modal dialog and handles native Escape cancellation', () => {
  const close = vi.fn()
  render(<QueryClientProvider client={createQueryClient()}><ItemModal item={{}} onClose={close} /></QueryClientProvider>)
  const dialog = screen.getByRole('dialog', { name: 'Add item' })
  fireEvent(dialog, new Event('cancel', { cancelable: true }))
  expect(close).toHaveBeenCalledOnce()
})
