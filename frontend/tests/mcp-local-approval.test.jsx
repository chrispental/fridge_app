// @vitest-environment-options {"url":"http://127.0.0.1:18080"}
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { api } from '../src/api/client.js'
import McpApprovalPage from '../src/pages/McpApprovalPage.jsx'

vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ authEnabled: false, session: null }) }))

const pending = {
  approval_id: 'local-approval', client_id: 'fridge-local-client', plan_id: 42,
  status: 'pending', expires_at: '2099-10-12T12:45:00Z', already_imported: false,
  meals: [{ id: 1, slot_index: 0, title: 'Tomato pasta', status: 'suggested' }],
  changes: [{ name: 'tomatoes', unit: 'can', operation: 'create', quantity: 2, added_quantity: 2, previous_quantity: null }],
  have: [], check: [], staples_assumed: [],
}

const clients = []
function page() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  clients.push(client)
  return <QueryClientProvider client={client}>
    <MemoryRouter initialEntries={['/mcp-approvals/local-approval']}>
      <Routes>
        <Route path="/mcp-approvals/:approvalId" element={<McpApprovalPage />} />
        <Route path="/shopping" element={<h1>Your shopping list</h1>} />
      </Routes>
    </MemoryRouter>
  </QueryClientProvider>
}

beforeEach(() => {
  vi.spyOn(api, 'getMcpApproval').mockResolvedValue(pending)
  vi.spyOn(api, 'approveMcpApproval').mockResolvedValue({ ...pending, status: 'approved' })
  vi.spyOn(api, 'denyMcpApproval').mockResolvedValue({ ...pending, status: 'rejected' })
})
afterEach(() => clients.splice(0).forEach((client) => client.clear()))

it('shows a no-login local review and its trust limit without approving on load', async () => {
  render(page())
  await screen.findByRole('button', { name: 'Approve these changes' })
  expect(window.location.origin).toBe('http://127.0.0.1:18080')
  expect(screen.getByText('fridge-local-client')).toBeTruthy()
  expect(screen.getByText('New item: 2 can')).toBeTruthy()
  const warning = screen.getByLabelText('Local approval limits')
  expect(warning.textContent).toContain('No login is required')
  expect(warning.textContent).toContain('accidental changes only')
  expect(warning.textContent).toContain('Trusted programs running on this computer can approve requests too')
  expect(screen.queryByText('Your account:')).toBeNull()
  expect(api.approveMcpApproval).not.toHaveBeenCalled()
  expect(api.denyMcpApproval).not.toHaveBeenCalled()
})

it('approves and revokes locally only after each explicit click', async () => {
  const importPlan = vi.spyOn(api, 'importPlanToList')
  render(page())
  fireEvent.click(await screen.findByRole('button', { name: 'Approve these changes' }))
  const revoke = await screen.findByRole('button', { name: 'Revoke approval' })
  expect(api.approveMcpApproval).toHaveBeenCalledExactlyOnceWith('local-approval')
  expect(api.denyMcpApproval).not.toHaveBeenCalled()
  expect(screen.getByRole('status').textContent).toContain('Waiting for the client')
  fireEvent.click(revoke)
  await screen.findByText('Request declined. The client cannot use this approval.')
  expect(api.denyMcpApproval).toHaveBeenCalledExactlyOnceWith('local-approval')
  expect(screen.queryByRole('button', { name: 'Approve these changes' })).toBeNull()
  expect(importPlan).not.toHaveBeenCalled()
})

it('can decline a local pending request without ever approving it', async () => {
  render(page())
  fireEvent.click(await screen.findByRole('button', { name: 'Decline request' }))
  await screen.findByText('Request declined. The client cannot use this approval.')
  expect(api.denyMcpApproval).toHaveBeenCalledExactlyOnceWith('local-approval')
  expect(api.approveMcpApproval).not.toHaveBeenCalled()
})

it('explains unavailable local approvals without asking the user to sign in', async () => {
  api.getMcpApproval.mockRejectedValue(Object.assign(new Error('Not found'), { status: 404 }))
  render(page())
  await screen.findByRole('alert')
  expect(screen.getByText(/unavailable in this local kitchen.*local MCP is enabled/)).toBeTruthy()
  expect(screen.queryByText(/signed in/)).toBeNull()
  expect(screen.queryByRole('button', { name: 'Approve these changes' })).toBeNull()
  expect(api.approveMcpApproval).not.toHaveBeenCalled()
  expect(api.denyMcpApproval).not.toHaveBeenCalled()
})

it('does not replay an uncertain local decision and requires an explicit successful refresh', async () => {
  api.approveMcpApproval.mockRejectedValueOnce(new Error('Connection lost'))
  render(page())
  fireEvent.click(await screen.findByRole('button', { name: 'Approve these changes' }))
  await screen.findByRole('alert')
  await waitFor(() => expect(screen.getByRole('button', { name: 'Reload approval' }).disabled).toBe(false))
  expect(screen.getByRole('button', { name: 'Approve these changes' }).disabled).toBe(true)
  expect(api.approveMcpApproval).toHaveBeenCalledOnce()
  api.getMcpApproval.mockResolvedValue({ ...pending, status: 'approved' })
  fireEvent.click(screen.getByRole('button', { name: 'Reload approval' }))
  await screen.findByRole('button', { name: 'Revoke approval' })
  await waitFor(() => expect(screen.queryByRole('alert')).toBeNull())
  expect(api.approveMcpApproval).toHaveBeenCalledOnce()
})
