import { beforeEach, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'

const state = vi.hoisted(() => ({
  auth: { authEnabled: true, session: null, loading: false },
  status: { isPending: false, data: { onboarded: true } },
  signInWithPassword: vi.fn(), signInWithOtp: vi.fn(), signUp: vi.fn(),
}))
vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => state.auth }))
vi.mock('../src/auth/supabase.js', () => ({ supabase: { auth: {
  signInWithPassword: state.signInWithPassword, signInWithOtp: state.signInWithOtp, signUp: state.signUp,
} } }))
vi.mock('../src/api/queries.js', () => ({ useOnboardStatus: () => state.status }))
vi.mock('../src/pages/Onboarding.jsx', () => ({ default: () => <h1>Set up your kitchen</h1> }))
vi.mock('../src/pages/McpApprovalPage.jsx', () => ({ default: () => <h1>Shopping approval review</h1> }))
vi.mock('../src/components/Nav.jsx', () => ({ default: () => null }))
vi.mock('../src/components/ResumeCooking.jsx', () => ({ default: () => null }))
vi.mock('../src/components/CookingProvider.jsx', () => ({ default: ({ children }) => children }))
import App from '../src/App.jsx'
import Login from '../src/pages/Login.jsx'

function Location() {
  const { pathname } = useLocation()
  return <output aria-label="Current path">{pathname}</output>
}
const path = '/mcp-approvals/approval-one'
const page = () => <MemoryRouter initialEntries={[path]}><Location /><App /></MemoryRouter>

beforeEach(() => {
  state.auth = { authEnabled: true, session: null, loading: false }
  state.status = { isPending: false, data: { onboarded: true } }
  state.signInWithPassword.mockReset().mockResolvedValue({ error: null })
  state.signInWithOtp.mockReset().mockResolvedValue({ error: null })
  state.signUp.mockReset().mockResolvedValue({ error: null })
})

it('keeps the approval URL through signed-out, password sign-in and onboarding gates', async () => {
  const view = render(page())
  expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeTruthy()
  expect(screen.queryByRole('heading', { name: 'Shopping approval review' })).toBeNull()
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'owner@example.test' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'test-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in', exact: true }))
  await waitFor(() => expect(state.signInWithPassword).toHaveBeenCalledOnce())
  state.auth = { ...state.auth, session: { user: { id: 'owner' } } }
  state.status = { isPending: false, data: { onboarded: false } }
  view.rerender(page())
  expect(screen.getByRole('heading', { name: 'Set up your kitchen' })).toBeTruthy()
  expect(screen.getByLabelText('Current path').textContent).toBe(path)
  state.status = { isPending: false, data: { onboarded: true } }
  view.rerender(page())
  expect(screen.getByRole('heading', { name: 'Shopping approval review' })).toBeTruthy()
  expect(screen.getByLabelText('Current path').textContent).toBe(path)
})

it('keeps only the first-party approval path for magic links, stripping queries and hashes', async () => {
  render(<MemoryRouter initialEntries={[`${path}?redirect=https://untrusted.example#secret`]}><Login /></MemoryRouter>)
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'owner@example.test' } })
  fireEvent.click(screen.getByRole('button', { name: 'Email me a magic link instead' }))
  await waitFor(() => expect(state.signInWithOtp).toHaveBeenCalledWith({
    email: 'owner@example.test', options: { emailRedirectTo: window.location.origin + path },
  }))
})

it('keeps the approval path for new-account email confirmation too', async () => {
  render(<MemoryRouter initialEntries={[path]}><Login /></MemoryRouter>)
  fireEvent.click(screen.getByRole('button', { name: 'Create an account' }))
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'owner@example.test' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'test-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Create account', exact: true }))
  await waitFor(() => expect(state.signUp).toHaveBeenCalledWith({
    email: 'owner@example.test', password: 'test-password', options: { emailRedirectTo: window.location.origin + path },
  }))
})

it.each(['/shopping', '/mcp-approvals/id/extra', '/mcp-approvals/%2F%2Fevil.example'])('does not preserve an arbitrary or malformed redirect path: %s', async (pathname) => {
  render(<MemoryRouter initialEntries={[pathname]}><Login /></MemoryRouter>)
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'owner@example.test' } })
  fireEvent.click(screen.getByRole('button', { name: 'Email me a magic link instead' }))
  await waitFor(() => expect(state.signInWithOtp).toHaveBeenCalledWith({
    email: 'owner@example.test', options: { emailRedirectTo: window.location.origin },
  }))
})
