import { useEffect, useState } from 'react'
import { BookOpen, Link2, ClipboardPaste, Search, Save } from 'lucide-react'
import MealCard from '../components/MealCard.jsx'
import { useDeliveryStatus, useImportRecipe, useRecipes } from '../api/queries.js'
import { toast } from '../components/toast.js'
import { PageHeader, HeroPanel, SegmentedControl, EmptyState, Skeleton } from '../components/ui.jsx'

const SOURCES = [
  { value: 'url', label: 'From a web address' },
  { value: 'text', label: 'Paste a recipe' },
]
const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'saved', label: 'Imported' },
  { value: 'favorite', label: 'Favourites' },
]

const fmtDate = (iso) => (iso ? new Date(iso + 'Z').toLocaleDateString() : null)

// The recipe book: recipes imported from the web or pasted in, plus anything
// marked favourite. Cooking one logs a copy to history; the book entry stays.
export default function RecipesPage() {
  const [source, setSource] = useState('url')
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [q, setQ] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setQ(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search])

  const recipesQ = useRecipes(q)
  const deliveryQ = useDeliveryStatus()
  const importMutation = useImportRecipe()

  const delivery = deliveryQ.data
  const deliveryAvailable = delivery ? !delivery.used : true
  const nextDeliveryDate = fmtDate(delivery?.next_available_at)

  const canSubmit = source === 'url' ? url.trim().length > 0 : text.trim().length >= 20

  function submit(e) {
    e.preventDefault()
    if (!canSubmit || importMutation.isPending) return
    importMutation.mutate(source === 'url' ? { url: url.trim() } : { text: text.trim() }, {
      onSuccess: (meal) => {
        toast.success(`Saved ${meal.title} to your recipes`)
        setUrl('')
        setText('')
      },
    })
  }

  const all = recipesQ.data || []
  const recipes = all.filter((m) =>
    filter === 'saved' ? m.status === 'saved' : filter === 'favorite' ? m.favorite : true,
  )

  return (
    <div>
      <PageHeader
        eyebrow="Recipe book"
        title="My recipes"
        subtitle="Recipes you've saved from the web or pasted in, plus your favourites. The chef can pick from your favourites when they fit what's in the fridge."
      />

      <HeroPanel compact>
        <form className="hero-field import-box" style={{ maxWidth: '100%' }} onSubmit={submit}>
          <SegmentedControl options={SOURCES} value={source} onChange={setSource} />
          {source === 'url' ? (
            <input
              type="url"
              className="idea-input"
              aria-label="Recipe web address"
              placeholder="https://example.com/best-lemon-chicken"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={importMutation.isPending}
            />
          ) : (
            <textarea
              className="idea-input"
              aria-label="Recipe text"
              placeholder="Paste the recipe here — title, ingredients and steps."
              value={text}
              onChange={(e) => setText(e.target.value)}
              disabled={importMutation.isPending}
            />
          )}
          <div className="import-actions">
            <button type="submit" className="btn primary" disabled={!canSubmit || importMutation.isPending}>
              {source === 'url' ? <Link2 size={16} strokeWidth={2.2} /> : <ClipboardPaste size={16} strokeWidth={2.2} />}
              {importMutation.isPending ? 'Saving…' : 'Save recipe'}
            </button>
            <span className="hint">
              {source === 'url'
                ? 'Most recipe pages are read directly; the rest are transcribed by the chef.'
                : 'The chef transcribes it into ingredients and steps you can check.'}
            </span>
          </div>
          {importMutation.isPending && <p className="hint">Reading the recipe — this can take a few seconds.</p>}
          {importMutation.error && <div className="banner error" role="alert">{importMutation.error.message}</div>}
        </form>
      </HeroPanel>

      {recipesQ.isError && <div className="banner error">{recipesQ.error.message}</div>}

      <div className="inv-toolbar">
        <div className="search-box">
          <Search size={15} strokeWidth={2.2} />
          <input
            type="search"
            placeholder="Search your recipes…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search recipes"
          />
        </div>
        <SegmentedControl options={FILTERS} value={filter} onChange={setFilter} />
      </div>

      {recipesQ.isPending ? (
        <div className="meal-results">
          <Skeleton height={360} radius={20} />
          <Skeleton height={360} radius={20} />
        </div>
      ) : recipes.length === 0 ? (
        <EmptyState
          icon={filter === 'favorite' ? <Save size={22} strokeWidth={2} /> : <BookOpen size={22} strokeWidth={2} />}
          title={q ? 'No matches' : filter === 'favorite' ? 'No favourites yet' : 'Your recipe book is empty'}
          message={
            q
              ? `No recipes match “${q}”.`
              : filter === 'favorite'
                ? 'Tap the heart on any meal to keep it here.'
                : 'Save a recipe from a web address or paste one in above.'
          }
        />
      ) : (
        <div className="meal-results">
          {recipes.map((m) => (
            <MealCard
              key={m.id}
              meal={m}
              deliveryAvailable={deliveryAvailable}
              nextDeliveryDate={nextDeliveryDate}
            />
          ))}
        </div>
      )}
    </div>
  )
}
