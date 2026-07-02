import { useEffect, useState } from 'react'
import { Truck, ChefHat, CalendarDays, History, Search } from 'lucide-react'
import MealCard from '../components/MealCard.jsx'
import { useDeliveryStatus, useInfiniteMeals } from '../api/queries.js'
import { PageHeader, SegmentedControl, Skeleton, EmptyState } from '../components/ui.jsx'

const FILTERS = [
  { value: '', label: 'All' },
  { value: 'cooked', label: 'Cooked' },
  { value: 'suggested', label: 'Suggested' },
]

const fmtDate = (iso) => (iso ? new Date(iso + 'Z').toLocaleDateString() : null)

export default function HistoryPage() {
  const [filter, setFilter] = useState('')
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('') // debounced

  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search])

  const mealsQ = useInfiniteMeals({ status: filter, q })
  const deliveryQ = useDeliveryStatus()

  const delivery = deliveryQ.data
  const deliveryAvailable = delivery ? !delivery.used : true
  const nextDeliveryDate = fmtDate(delivery?.next_available_at)

  const meals = mealsQ.data?.pages.flat()

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

      {mealsQ.isError && <div className="banner error">{mealsQ.error.message}</div>}

      <div className="inv-toolbar">
        <div className="search-box">
          <Search size={15} strokeWidth={2.2} />
          <input
            type="search"
            placeholder="Search meals…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search meal history"
          />
        </div>
        <SegmentedControl options={FILTERS} value={filter} onChange={setFilter} />
      </div>

      {mealsQ.isPending ? (
        <div className="stack" style={{ gap: 18, marginTop: 18 }}>
          <Skeleton height={360} radius={20} />
          <Skeleton height={360} radius={20} />
          <Skeleton height={360} radius={20} />
        </div>
      ) : meals.length === 0 ? (
        <EmptyState
          icon={<History size={22} strokeWidth={2} />}
          title={q ? 'No matches' : 'No meals yet'}
          message={
            q
              ? `No meals match “${q}”.`
              : "Once you get a suggestion or cook something, it'll show up here."
          }
        />
      ) : (
        <>
          <div className="stack" style={{ gap: 18, marginTop: 18 }}>
            {meals.map((m) => (
              <div key={m.id}>
                <MealCard
                  meal={m}
                  deliveryAvailable={deliveryAvailable}
                  nextDeliveryDate={nextDeliveryDate}
                />
                <div className="ts">{tsLine(m)}</div>
              </div>
            ))}
          </div>
          {mealsQ.hasNextPage && (
            <div style={{ display: 'flex', justifyContent: 'center', marginTop: 20 }}>
              <button
                className="btn"
                onClick={() => mealsQ.fetchNextPage()}
                disabled={mealsQ.isFetchingNextPage}
              >
                {mealsQ.isFetchingNextPage ? 'Loading…' : 'Load more'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
