import { TimerContext } from './timerContext.js'
import { useTimerStore } from './useTimers.js'
import { useAuth } from '../auth/useAuth.js'
import { kitchenKey } from '../utils/storage.js'

export default function CookingProvider({ children }) {
  const { session } = useAuth()
  const store = useTimerStore(kitchenKey(session?.user?.id, 'timers', 'all'))
  return <TimerContext.Provider value={store}>{children}</TimerContext.Provider>
}
