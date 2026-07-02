import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Nav from './components/Nav.jsx'
import { useOnboardStatus } from './api/queries.js'
import { PageSkeleton } from './components/ui.jsx'
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

export default function App() {
  const location = useLocation()
  const status = useOnboardStatus()

  if (status.isPending) {
    return (
      <div className="app">
        <main className="content">
          <PageSkeleton />
        </main>
      </div>
    )
  }

  // An unreachable backend reads as "not onboarded" — same as before React Query.
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
    <div className="app">
      <Nav />
      <main className="content">
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
  )
}
