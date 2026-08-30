import { useState } from 'react'
import { supabase } from '../auth/supabase.js'

// Email + password sign-in / sign-up with a magic-link alternative. Rendered only in
// cloud mode (AuthProvider), before the onboarding gate. Reuses the onboarding shell
// so it reads as the same welcome flow.
export default function Login() {
  const [mode, setMode] = useState('signin') // signin | signup
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const run = async (fn) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const { error: err } = await fn()
      if (err) setError(err.message)
      return !err
    } catch (e) {
      setError(e.message || 'Something went wrong')
      return false
    } finally {
      setBusy(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    if (mode === 'signin') {
      await run(() => supabase.auth.signInWithPassword({ email, password }))
    } else {
      const ok = await run(() => supabase.auth.signUp({ email, password }))
      if (ok) setNotice('Account created. Check your email to confirm, then sign in.')
    }
  }

  const magicLink = async () => {
    if (!email) {
      setError('Enter your email first.')
      return
    }
    const ok = await run(() =>
      supabase.auth.signInWithOtp({
        email,
        options: { emailRedirectTo: window.location.origin },
      }),
    )
    if (ok) setNotice('Magic link sent — check your email.')
  }

  return (
    <div className="onboarding">
      <div className="onboarding-card login-card">
        <div className="onboarding-badge">
          <img src="/logo-mark.png" alt="" width="76" height="76" />
        </div>
        <h1>{mode === 'signin' ? 'Welcome back' : 'Create your account'}</h1>
        <p>
          {mode === 'signin'
            ? 'Sign in to get to your fridge, plans, and shopping list.'
            : 'Your inventory and preferences are private to your account.'}
        </p>

        <form onSubmit={submit} className="login-form">
          <div className="field">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && <div className="banner error">{error}</div>}
          {notice && <div className="banner success">{notice}</div>}

          <button type="submit" className="btn primary big block" disabled={busy}>
            {busy ? 'One moment…' : mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>
        </form>

        <div className="login-alt">
          <button type="button" className="btn ghost block" onClick={magicLink} disabled={busy}>
            Email me a magic link instead
          </button>
          <p className="hint">
            {mode === 'signin' ? 'New here? ' : 'Already have an account? '}
            <button
              type="button"
              className="link-btn"
              onClick={() => {
                setMode(mode === 'signin' ? 'signup' : 'signin')
                setError(null)
                setNotice(null)
              }}
            >
              {mode === 'signin' ? 'Create an account' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
