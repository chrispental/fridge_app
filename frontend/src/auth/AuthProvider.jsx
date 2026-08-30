import { useEffect, useMemo, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { AUTH_ENABLED, supabase } from './supabase.js'
import { AuthContext } from './context.js'
import { configureAuth } from '../api/client.js'

// Owns the Supabase session and wires it into the API client. In local mode it is a
// no-op shell: no session, never loading, and supabase-js is never touched.
export function AuthProvider({ children }) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(AUTH_ENABLED)
  const lastUserId = useRef(null)

  useEffect(() => {
    if (!AUTH_ENABLED) return undefined

    configureAuth({
      getToken: async () => {
        const { data } = await supabase.auth.getSession() // auto-refreshed
        return data.session?.access_token ?? null
      },
      // The backend rejected a token we sent: the session is unusable, drop it.
      handleUnauthorized: () => supabase.auth.signOut(),
    })

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session)
      lastUserId.current = data.session?.user?.id ?? null
      setLoading(false)
    })

    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      const nextId = next?.user?.id ?? null
      // Sign-out or a different account: nothing cached may survive.
      if (nextId !== lastUserId.current) queryClient.clear()
      lastUserId.current = nextId
      setSession(next)
      setLoading(false)
    })
    return () => sub.subscription.unsubscribe()
  }, [queryClient])

  const value = useMemo(
    () => ({
      authEnabled: AUTH_ENABLED,
      session,
      loading,
      signOut: async () => {
        if (supabase) await supabase.auth.signOut()
      },
    }),
    [session, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
