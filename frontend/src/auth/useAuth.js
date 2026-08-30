import { useContext } from 'react'
import { AuthContext } from './context.js'

export const useAuth = () => useContext(AuthContext)
