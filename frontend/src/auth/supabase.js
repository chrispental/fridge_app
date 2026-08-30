// Supabase browser client. Only exists in cloud mode — when the build was given
// VITE_SUPABASE_URL + VITE_SUPABASE_PUBLISHABLE_KEY. Without them the app runs in
// single-user local mode with no login (the backend mirrors this via SUPABASE_URL).
//
// Only VITE_-prefixed vars reach the bundle, so backend secrets can't leak here.
import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY

export const AUTH_ENABLED = Boolean(url && key)

export const supabase = AUTH_ENABLED
  ? createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true } })
  : null
