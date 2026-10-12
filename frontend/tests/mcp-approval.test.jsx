import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { Link, MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { api, configureAuth } from '../src/api/client.js'
import McpApprovalPage from '../src/pages/McpApprovalPage.jsx'

const auth = vi.hoisted(() => ({
  authEnabled: true, session: { user: { id: 'owner', email: 'owner@example.test' } },
}))
vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => auth }))

const pending = {
  approval_id: 'approval-one', client_id: 'meal-helper', plan_id: 42,
  status: 'pending', expires_at: '2099-10-12T12:45:00Z', already_imported: false,
  meals: [{ id: 1, slot_index: 0, title: '<img src=x onerror=alert(1)> Pasta', status: 'suggested' }],
  changes: [
    { name: 'tomatoes', unit: 'can', operation: 'create', quantity: 2, added_quantity: 2, previous_quantity: null },
    { name: 'olive oil', unit: 'cup', operation: 'update', quantity: 0.875, added_quantity: 0.125, previous_quantity: 0.75 },
    { name: 'spinach', unit: 'bunch', operation: 'create', quantity: null, added_quantity: null, previous_quantity: null },
  ],
  to_buy: [], have: [{ name: 'rice', quantity: 1, unit: 'cup' }],
  check: [{ name: 'salt', quantity: null, unit: 'unknown' }], staples_assumed: ['water'],
}

const clients = []
function Navigation() {
  const navigate = useNavigate()
  const location = useLocation()
  return <><span aria-label="Current path">{location.pathname}</span><button onClick={() => navigate(-1)}>Browser back</button></>
}
function page(initialEntries = ['/mcp-approvals/approval-one']) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  clients.push(client)
  return {
    client,
    ui: <QueryClientProvider client={client}><MemoryRouter initialEntries={initialEntries}>
      <Navigation />
      <Routes>
        <Route path="/mcp-approvals/:approvalId" element={<><McpApprovalPage /><Link to="/mcp-approvals/approval-two">Next approval</Link></>} />
        <Route path="/shopping" element={<h1>Your shopping list</h1>} />
      </Routes>
    </MemoryRouter></QueryClientProvider>,
  }
}

beforeEach(() => {
  auth.authEnabled = true
  auth.session = { user: { id: 'owner', email: 'owner@example.test' } }
  vi.spyOn(api, 'getMcpApproval').mockResolvedValue(pending)
  vi.spyOn(api, 'approveMcpApproval').mockResolvedValue({ ...pending, status: 'approved' })
  vi.spyOn(api, 'denyMcpApproval').mockResolvedValue({ ...pending, status: 'rejected' })
})
afterEach(() => {
  clients.splice(0).forEach((client) => client.clear())
  configureAuth({ getToken: async () => null, handleUnauthorized: () => {} })
  vi.unstubAllGlobals()
})

it('shows the exact delta, account, client, expiry and escaped recipe text without approving', async () => {
  const { ui } = page()
  const view = render(ui)
  await screen.findByRole('button', { name: 'Approve these changes' })
  expect(screen.getByText('meal-helper')).toBeTruthy()
  expect(screen.getByText('owner@example.test')).toBeTruthy()
  expect(screen.getByText(pending.meals[0].title)).toBeTruthy()
  expect(view.container.querySelector('img')).toBeNull()
  expect(screen.getByText('Currently: 0.75 cup')).toBeTruthy()
  expect(screen.getByText('Add: 0.125 cup')).toBeTruthy()
  expect(screen.getByText('After import: 0.875 cup')).toBeTruthy()
  expect(screen.getByText('New item: Unknown amount (bunch)')).toBeTruthy()
  expect(screen.getByText('salt: Unknown amount')).toBeTruthy()
  expect(screen.getByText(/They are excluded from this import/)).toBeTruthy()
  expect(view.container.querySelector('time').getAttribute('datetime')).toBe(pending.expires_at)
  expect(api.approveMcpApproval).not.toHaveBeenCalled()
  expect(api.denyMcpApproval).not.toHaveBeenCalled()
  expect(screen.queryByLabelText('Local approval limits')).toBeNull()
})

it('approves only after an explicit click and blocks repeated decisions while the request is pending', async () => {
  let finish
  api.approveMcpApproval.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  const importPlan = vi.spyOn(api, 'importPlanToList')
  const { ui } = page()
  render(ui)
  const approve = await screen.findByRole('button', { name: 'Approve these changes' })
  fireEvent.click(approve)
  fireEvent.click(approve)
  await waitFor(() => expect(api.approveMcpApproval).toHaveBeenCalledOnce())
  expect(screen.getByRole('button', { name: 'Decline request' }).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: 'Decline request' }))
  expect(api.denyMcpApproval).not.toHaveBeenCalled()
  await act(async () => finish({ ...pending, status: 'approved' }))
  await screen.findByRole('button', { name: 'Revoke approval' })
  expect(screen.getByRole('status').textContent).toContain('Waiting for the client')
  expect(screen.queryByRole('button', { name: 'Approve these changes' })).toBeNull()
  expect(screen.getByRole('button', { name: 'Revoke approval' })).toBeTruthy()
  expect(importPlan).not.toHaveBeenCalled()
})

it('declines or revokes only when the user requests it', async () => {
  api.getMcpApproval.mockResolvedValue({ ...pending, status: 'approved' })
  const { ui } = page()
  render(ui)
  fireEvent.click(await screen.findByRole('button', { name: 'Revoke approval' }))
  await screen.findByText('Request declined. The client cannot use this approval.')
  expect(api.denyMcpApproval).toHaveBeenCalledExactlyOnceWith('approval-one')
  expect(api.approveMcpApproval).not.toHaveBeenCalled()
})

it('lets a user leave and return without approving or denying', async () => {
  const { ui } = page()
  render(ui)
  await screen.findByRole('button', { name: 'Approve these changes' })
  fireEvent.click(screen.getByRole('link', { name: 'Back to shopping list' }))
  await screen.findByRole('heading', { name: 'Your shopping list' })
  fireEvent.click(screen.getByRole('button', { name: 'Browser back' }))
  await screen.findByRole('button', { name: 'Approve these changes' })
  expect(screen.getByLabelText('Current path').textContent).toBe('/mcp-approvals/approval-one')
  expect(api.approveMcpApproval).not.toHaveBeenCalled()
  expect(api.denyMcpApproval).not.toHaveBeenCalled()
})

it.each(['approved', 'consumed', 'rejected', 'expired', 'stale'])('reloads a %s receipt without offering approval again', async (status) => {
  api.getMcpApproval.mockResolvedValue({ ...pending, status })
  const first = page()
  const view = render(first.ui)
  await screen.findByRole('status')
  view.unmount()
  render(page().ui)
  await screen.findByRole('status')
  expect(screen.queryByRole('button', { name: 'Approve these changes' })).toBeNull()
  expect(api.approveMcpApproval).not.toHaveBeenCalled()
})

it('expires an open preview before accepting another click', async () => {
  let tick
  const time = vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-12T12:00:00Z'))
  vi.spyOn(window, 'setInterval').mockImplementation((callback) => { tick = callback; return 123 })
  api.getMcpApproval.mockResolvedValue({ ...pending, expires_at: '2026-10-12T12:00:05Z' })
  render(page().ui)
  await screen.findByRole('button', { name: 'Approve these changes' })
  time.mockReturnValue(Date.parse('2026-10-12T12:00:06Z'))
  act(() => tick())
  expect(screen.getByRole('status').textContent).toContain('expired')
  expect(screen.queryByRole('button', { name: 'Approve these changes' })).toBeNull()
  expect(api.approveMcpApproval).not.toHaveBeenCalled()
})

it('rejects a click after expiry even when the visible clock has not ticked yet', async () => {
  const time = vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-10-12T12:00:00Z'))
  // Simulate a backgrounded tab whose display timer has not run again.
  vi.spyOn(window, 'setInterval').mockReturnValue(123)
  api.getMcpApproval.mockResolvedValue({ ...pending, expires_at: '2026-10-12T12:00:05Z' })
  render(page().ui)
  const approve = await screen.findByRole('button', { name: 'Approve these changes' })
  expect(approve.disabled).toBe(false)
  time.mockReturnValue(Date.parse('2026-10-12T12:00:06Z'))
  fireEvent.click(approve)
  expect(screen.getByRole('status').textContent).toContain('expired')
  expect(api.approveMcpApproval).not.toHaveBeenCalled()
})

it('does not retry an uncertain decision until a successful explicit status reload', async () => {
  api.approveMcpApproval.mockRejectedValueOnce(new Error('Connection lost'))
  render(page().ui)
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

it('shows stale status after a conflict and never retries the write', async () => {
  api.approveMcpApproval.mockImplementation(async () => {
    api.getMcpApproval.mockResolvedValue({ ...pending, status: 'stale' })
    throw Object.assign(new Error('Preview changed'), { status: 409 })
  })
  render(page().ui)
  fireEvent.click(await screen.findByRole('button', { name: 'Approve these changes' }))
  await screen.findByText(/Your kitchen changed after this preview/)
  expect(screen.queryByRole('button', { name: 'Approve these changes' })).toBeNull()
  expect(api.approveMcpApproval).toHaveBeenCalledOnce()
})

it('keeps another user’s approval unavailable and allows a safe retry after an error', async () => {
  api.getMcpApproval.mockRejectedValueOnce(Object.assign(new Error('Not found'), { status: 404 }))
  render(page().ui)
  await screen.findByText(/unavailable for your account/)
  expect(screen.queryByRole('button', { name: 'Approve these changes' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Reload approval' }))
  await screen.findByRole('button', { name: 'Approve these changes' })
  expect(api.approveMcpApproval).not.toHaveBeenCalled()
})

it('does not let completion of an older decision affect a newer approval route', async () => {
  let finish
  api.approveMcpApproval.mockImplementation(() => new Promise((resolve) => { finish = resolve }))
  api.getMcpApproval.mockImplementation(async (id) => ({ ...pending, approval_id: id, client_id: id === 'approval-two' ? 'second-client' : 'meal-helper' }))
  render(page().ui)
  fireEvent.click(await screen.findByRole('button', { name: 'Approve these changes' }))
  await waitFor(() => expect(api.approveMcpApproval).toHaveBeenCalledOnce())
  fireEvent.click(screen.getByRole('link', { name: 'Next approval' }))
  await screen.findByText('second-client')
  await act(async () => finish({ ...pending, status: 'approved' }))
  expect(screen.getByText('second-client')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Approve these changes' })).toBeTruthy()
  expect(screen.getByLabelText('Current path').textContent).toBe('/mcp-approvals/approval-two')
})

it('does not fetch or offer local approval outside the canonical loopback origin', () => {
  auth.authEnabled = false
  auth.session = null
  render(page().ui)
  expect(screen.getByRole('heading', { name: 'Shopping approval unavailable' })).toBeTruthy()
  expect(screen.getByText(/Local client approvals are available only at http:\/\/127.0.0.1:18080/)).toBeTruthy()
  expect(api.getMcpApproval).not.toHaveBeenCalled()
})

it('does not fetch or offer cloud approval while signed out', () => {
  auth.session = null
  render(page().ui)
  expect(screen.getByRole('heading', { name: 'Shopping approval unavailable' })).toBeTruthy()
  expect(screen.getByText(/require a signed-in cloud kitchen/)).toBeTruthy()
  expect(api.getMcpApproval).not.toHaveBeenCalled()
})

describe('approval API calls', () => {
  it('uses the app token, encodes the ID and marks explicit first-party decisions', async () => {
    // Restore the real methods for this request-layer regression.
    api.getMcpApproval.mockRestore()
    api.approveMcpApproval.mockRestore()
    api.denyMcpApproval.mockRestore()
    configureAuth({ getToken: async () => 'test-app-session' })
    const fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, text: async () => JSON.stringify(pending) })
    vi.stubGlobal('fetch', fetch)
    await api.getMcpApproval('id/with?parts')
    await api.approveMcpApproval('approval-one')
    await api.denyMcpApproval('approval-one')
    expect(fetch.mock.calls.map(([url]) => url)).toEqual([
      '/api/mcp-approvals/id%2Fwith%3Fparts', '/api/mcp-approvals/approval-one/approve', '/api/mcp-approvals/approval-one/deny',
    ])
    for (const [, options] of fetch.mock.calls) expect(options.headers.get('Authorization')).toBe('Bearer test-app-session')
    expect(fetch.mock.calls[0][1].headers.has('X-Fridge-MCP-Approval')).toBe(false)
    for (const [, options] of fetch.mock.calls.slice(1)) {
      expect(options.method).toBe('POST')
      expect(options.headers.get('Content-Type')).toBe('application/json')
      expect(options.headers.get('X-Fridge-MCP-Approval')).toBe('1')
      expect(options.body).toBeUndefined()
    }
  })

  it('sends local decisions without a token and leaves Origin to the browser', async () => {
    api.approveMcpApproval.mockRestore()
    api.denyMcpApproval.mockRestore()
    configureAuth({ getToken: async () => null })
    const fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, text: async () => JSON.stringify(pending) })
    vi.stubGlobal('fetch', fetch)
    await api.approveMcpApproval('approval-one')
    await api.denyMcpApproval('approval-one')
    for (const [, options] of fetch.mock.calls) {
      expect(options.method).toBe('POST')
      expect(options.headers.has('Authorization')).toBe(false)
      expect(options.headers.has('Origin')).toBe(false)
      expect(options.headers.get('Content-Type')).toBe('application/json')
      expect(options.headers.get('X-Fridge-MCP-Approval')).toBe('1')
    }
  })
})
