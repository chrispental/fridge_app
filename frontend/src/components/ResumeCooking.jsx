import { useState } from 'react'
import { useAuth } from '../auth/useAuth.js'
import { useMeal, useCookMeal } from '../api/queries.js'
import { canResume, dismissActiveCook, useCookProgress } from '../utils/cookingProgress.js'
import CookMode from './CookMode.jsx'

export default function ResumeCooking() {
  const { session } = useAuth()
  const userId = session?.user?.id
  const active = useCookProgress(userId, 'active')
  const id = Number.isInteger(active?.id) && active.id > 0 ? active.id : null
  const progress = useCookProgress(userId, id)
  const mealQ = useMeal(id)
  const cook = useCookMeal()
  const [openMeal, setOpenMeal] = useState(null)
  const meal = mealQ.data
  const resumable = id && meal && canResume(progress, meal)
  return (
    <>
    {resumable && <div className="banner info resume-cooking">
      <button className="btn" onClick={() => setOpenMeal(meal)}>Resume cooking: {meal.title}</button>
      <button className="ghost" aria-label="Dismiss cooking reminder" onClick={() => dismissActiveCook(userId)}>Dismiss</button>
    </div>}
    {openMeal && <CookMode key={openMeal.id} meal={openMeal} onClose={() => setOpenMeal(null)}
      onCook={(decrement, requestId) => cook.mutateAsync({ id: openMeal.id, decrement, requestId })} />}
    </>
  )
}
