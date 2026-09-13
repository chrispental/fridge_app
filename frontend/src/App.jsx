import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Nav from './components/Nav.jsx'
import { useOnboardStatus } from './api/queries.js'
import { useAuth } from './auth/useAuth.js'
import { PageSkeleton } from './components/ui.jsx'
import Login from './pages/Login.jsx'
import Onboarding from './pages/Onboarding.jsx'
import Home from './pages/Home.jsx'
import SuggestMeal from './pages/SuggestMeal.jsx'
import WeekPlanPage from './pages/WeekPlanPage.jsx'
import InventoryPage from './pages/InventoryPage.jsx'
import PhotoCapture from './pages/PhotoCapture.jsx'
import ReviewExtraction from './pages/ReviewExtraction.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import PreferencesPage from './pages/PreferencesPage.jsx'
import ShoppingListPage from './pages/ShoppingListPage.jsx'
import InsightsPage from './pages/InsightsPage.jsx'
import QueryError from './components/QueryError.jsx'
import CookingProvider from './components/CookingProvider.jsx'

const Skeleton = () => (
  <div className="app">
    <main className="content">
      <PageSkeleton />
    </main>
  </div>
)

export default function App() {
  const location = useLocation()
  const { authEnabled, session, loading: authLoading } = useAuth()
  const signedIn = !authEnabled || Boolean(session)
  // Gate order: session (cloud mode only) → onboarding → app. The status query is
  // held back until there's a session, so an unauthenticated 401 never gets read as
  // "not onboarded".
  const status = useOnboardStatus({ enabled: signedIn })

  if (authEnabled && authLoading) return <Skeleton />

  if (!signedIn) {
    return (
      <div className="app">
        <Routes>
          <Route path="*" element={<Login />} />
        </Routes>
      </div>
    )
  }

  if (status.isPending) return <Skeleton />
  if (status.isError && !status.data) {
    return <main className="content"><QueryError query={status} /></main>
  }

  const onboarded = status.data?.onboarded ?? false

  if (!onboarded) {
    return (
      <div className="app">
        <Routes>
          <Route path="*" element={<Onboarding />} />
        </Routes>
      </div>
    )
  }

  return (
    <CookingProvider key={session?.user?.id || 'local'}>
    <div className="app">
      <Nav />
      <main className="content">
        {status.isError && <div className="banner error" role="status">Connection interrupted. Showing your saved kitchen.</div>}
        <div className="page-enter" key={location.pathname}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/cook" element={<SuggestMeal />} />
            <Route path="/plan" element={<WeekPlanPage />} />
            <Route path="/inventory" element={<InventoryPage />} />
            <Route path="/shopping" element={<ShoppingListPage />} />
            <Route path="/capture" element={<PhotoCapture />} />
            <Route path="/review/:batchId" element={<ReviewExtraction />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/insights" element={<InsightsPage />} />
            <Route path="/preferences" element={<PreferencesPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
    </div>
    </CookingProvider>
  )
}
