import { useEffect, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Nav from './components/Nav.jsx'
import { api } from './api/client.js'
import Onboarding from './pages/Onboarding.jsx'
import SuggestMeal from './pages/SuggestMeal.jsx'
import WeekPlanPage from './pages/WeekPlanPage.jsx'
import InventoryPage from './pages/InventoryPage.jsx'
import PhotoCapture from './pages/PhotoCapture.jsx'
import ReviewExtraction from './pages/ReviewExtraction.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import PreferencesPage from './pages/PreferencesPage.jsx'

export default function App() {
  // null = still loading, false = needs onboarding, true = onboarded
  const [onboarded, setOnboarded] = useState(null)

  useEffect(() => {
    api
      .getOnboardStatus()
      .then((s) => setOnboarded(s.onboarded))
      .catch(() => setOnboarded(false))
  }, [])

  if (onboarded === null) {
    return <div className="loading">Loading…</div>
  }

  if (!onboarded) {
    return (
      <div className="app">
        <Routes>
          <Route
            path="*"
            element={<Onboarding onDone={() => setOnboarded(true)} />}
          />
        </Routes>
      </div>
    )
  }

  return (
    <div className="app">
      <Nav />
      <main className="content">
        <Routes>
          <Route path="/" element={<SuggestMeal />} />
          <Route path="/plan" element={<WeekPlanPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/capture" element={<PhotoCapture />} />
          <Route path="/review/:batchId" element={<ReviewExtraction />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/preferences" element={<PreferencesPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
