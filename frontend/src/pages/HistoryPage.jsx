import { useEffect, useState } from 'react'
import { Truck, ChefHat, CalendarDays, History } from 'lucide-react'
import MealCard from '../components/MealCard.jsx'
import { api } from '../api/client.js'
import { PageHeader, SegmentedControl, Skeleton, EmptyState } from '../components/ui.jsx'

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'cooked', label: 'Cooked' },
  { value: 'suggested', label: 'Suggested' },
]

const fmtDate = (iso) => (iso ? new Date(iso + 'Z').toLocaleDateString() : null)

export default function HistoryPage() {
  const [meals, setMeals] = useState(null)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState(null)
  const [delivery, setDelivery] = useState(null)

  function load() {
    api
      .getMeals(filter || undefined)
      .then(setMeals)
      .catch((e) => setError(e.message))
  }
  useEffect(load, [filter])

  function loadDelivery() {
    api.getDeliveryStatus().then(setDelivery).catch(() => setDelivery(null))
  }
  useEffect(loadDelivery, [])

  const deliveryAvailable = delivery ? !delivery.used : true
  const nextDeliveryDate = fmtDate(delivery?.next_available_at)

  function onChanged() {
    load()
    loadDelivery()
  }

  function tsLine(m) {
    if (m.status === 'ordered' && m.delivery_ordered_at) {
      return (
        <>
          <Truck size={12} strokeWidth={2.4} style={{ verticalAlign: '-2px' }} />{' '}
          Ordered {new Date(m.delivery_ordered_at + 'Z').toLocaleDateString()}
        </>
      )
    }
    if (m.status === 'cooked' && m.cooked_at) {
      return (
        <>
          <ChefHat size={12} strokeWidth={2.4} style={{ verticalAlign: '-2px' }} />{' '}
          Cooked {new Date(m.cooked_at + 'Z').toLocaleDateString()}
        </>
      )
    }
    return (
      <>
        <CalendarDays size={12} strokeWidth={2.4} style={{ verticalAlign: '-2px' }} />{' '}
        Suggested {new Date(m.suggested_at + 'Z').toLocaleDateString()}
      </>
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="Your kitchen"
        title="Meal history"
        subtitle="Every suggestion is logged here — that's how meals avoid repeating."
      />

      {error && <div className="banner error">{error}</div>}

      <SegmentedControl options={FILTERS} value={filter} onChange={setFilter} />

      {!meals ? (
        <div className="stack" style={{ gap: 18, marginTop: 18 }}>
          <Skeleton height={360} radius={20} />
          <Skeleton height={360} radius={20} />
          <Skeleton height={360} radius={20} />
        </div>
      ) : meals.length === 0 ? (
        <EmptyState
          icon={<History size={22} strokeWidth={2} />}
          title="No meals yet"
          message="Once you get a suggestion or cook something, it'll show up here."
        />
      ) : (
        <div className="stack" style={{ gap: 18, marginTop: 18 }}>
          {meals.map((m) => (
            <div key={m.id}>
              <MealCard
                meal={m}
                onChanged={onChanged}
                deliveryAvailable={deliveryAvailable}
                nextDeliveryDate={nextDeliveryDate}
              />
              <div className="ts">{tsLine(m)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
