import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
const state = vi.hoisted(() => ({ query: {} }))
vi.mock('../src/api/queries.js', () => ({ useOnboardStatus: () => state.query }))
vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ authEnabled: false, session: null, loading: false }) }))
vi.mock('../src/pages/Home.jsx', () => ({ default: () => <p>Your kitchen dashboard</p> }))
vi.mock('../src/components/Nav.jsx', () => ({ default: () => <nav>Kitchen navigation</nav> }))
import App from '../src/App.jsx'

describe('connection recovery', () => {
  it('shows retry instead of onboarding after an initial API failure', () => {
    const refetch = vi.fn()
    state.query = { isError: true, isPending: false, refetch }
    render(<MemoryRouter><App /></MemoryRouter>)
    expect(screen.queryByText('Welcome to Fridge Chef')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(refetch).toHaveBeenCalledOnce()
  })
  it('keeps a cached kitchen visible when refreshing fails', () => {
    state.query = { isError: true, isPending: false, data: { onboarded: true } }
    render(<MemoryRouter><App /></MemoryRouter>)
    expect(screen.getByText('Your kitchen dashboard')).toBeTruthy()
    expect(screen.getByRole('status').textContent).toContain('Connection interrupted')
  })
})
