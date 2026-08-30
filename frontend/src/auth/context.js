import { createContext } from 'react'

// Shared between AuthProvider (writes) and useAuth (reads). Kept in its own file so
// AuthProvider.jsx only exports a component (React Fast Refresh requirement).
export const AuthContext = createContext({
  authEnabled: false,
  session: null,
  loading: false,
  signOut: async () => {},
})
