import { useState } from 'react'
import { it, expect, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
vi.mock('../src/auth/useAuth.js', () => ({ useAuth: () => ({ session: null }) }))
import CookingProvider from '../src/components/CookingProvider.jsx'
import CookMode from '../src/components/CookMode.jsx'
const meal = { id: 41, title: 'Rice bowl', recipe_json: { ingredients: [], steps: ['Simmer for 1 minute.'] } }
function Kitchen() {
  const [open, setOpen] = useState(true)
  return <CookingProvider><button onClick={() => setOpen(true)}>Resume cooking</button>{open && <CookMode meal={meal} onClose={() => setOpen(false)} onCook={vi.fn()} />}</CookingProvider>
}
it('keeps timers running after closing cook mode and restores the step after reload', () => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-09-13T12:00:00Z'))
  const resume = vi.fn(() => Promise.resolve())
  window.AudioContext = class { resume = resume; close = () => Promise.resolve() }
  let view = render(<Kitchen />)
  fireEvent.click(screen.getByRole('button', { name: 'Next' }))
  fireEvent.click(screen.getByRole('button', { name: 'Start timer' }))
  expect(resume).toHaveBeenCalledOnce()
  fireEvent.click(screen.getByRole('button', { name: 'Close cook mode' }))
  act(() => vi.advanceTimersByTime(10000))
  fireEvent.click(screen.getByRole('button', { name: 'Resume cooking' }))
  expect(screen.getByText('0:50')).toBeTruthy()
  view.unmount()
  act(() => vi.advanceTimersByTime(5000))
  view = render(<Kitchen />)
  act(() => vi.advanceTimersByTime(250))
  expect(screen.getByText('0:45')).toBeTruthy()
  expect(screen.getByText('Step 1 of 1')).toBeTruthy()
  view.unmount()
})
