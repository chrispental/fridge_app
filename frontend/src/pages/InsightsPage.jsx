import { Link } from 'react-router-dom'
import { ChefHat, Sparkles, Truck, ThumbsUp } from 'lucide-react'
import { useMealStats } from '../api/queries.js'
import {
  PageHeader, Bento, BentoItem, StatCard, SectionHeader, EmptyState, PageSkeleton,
} from '../components/ui.jsx'

function BarList({ rows }) {
  if (!rows || rows.length === 0) return <p className="hint">Not enough data yet.</p>
  const max = Math.max(...rows.map((r) => r.count), 1)
  return (
    <div className="bar-list">
      {rows.map((r) => (
        <div key={r.label} className="bar-row">
          <span className="bar-label">{r.label}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${(r.count / max) * 100}%` }} />
          </span>
          <span className="bar-count">{r.count}</span>
        </div>
      ))}
    </div>
  )
}

const fmtWeek = (iso) => {
  const [y, m, d] = (iso || '').slice(0, 10).split('-').map(Number)
  if (!y) return ''
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export default function InsightsPage() {
  const statsQ = useMealStats()

  if (statsQ.isPending) return <PageSkeleton />
  if (statsQ.isError) return <div className="banner error">{statsQ.error.message}</div>

  const stats = statsQ.data
  const { totals } = stats

  if (!totals || totals.total === 0) {
    return (
      <div>
        <PageHeader eyebrow="Your kitchen" title="Insights" subtitle="What you cook, what you love, and what you reach for." />
        <EmptyState
          icon={<ChefHat size={22} strokeWidth={2} />}
          title="No data yet"
          message="Cook a few meals and your kitchen stats will show up here."
          action={<Link to="/cook" className="btn primary">Get a suggestion</Link>}
        />
      </div>
    )
  }

  const weeks = (stats.cooks_per_week || []).map((w) => ({
    label: fmtWeek(w.week_start),
    count: w.count,
  }))
  const cuisines = (stats.cuisines || []).map((c) => ({ label: c.cuisine, count: c.count }))
  const ingredients = (stats.top_ingredients || []).map((i) => ({ label: i.name, count: i.count }))
  const tags = (stats.feedback_tags || []).map((t) => ({ label: t.tag, count: t.count }))

  return (
    <div className="wide">
      <PageHeader
        eyebrow="Your kitchen"
        title="Insights"
        subtitle="What you cook, what you love, and what you reach for."
      />

      <Bento>
        <BentoItem span={4}>
          <StatCard icon={<ChefHat size={20} strokeWidth={2} />} iconTone="success" title="Cooked">
            <div className="stat-row">
              <span className="stat-big">{totals.cooked}</span>
              <span className="caption">meals cooked</span>
            </div>
          </StatCard>
        </BentoItem>
        <BentoItem span={4}>
          <StatCard icon={<Sparkles size={20} strokeWidth={2} />} title="Suggested">
            <div className="stat-row">
              <span className="stat-big">{totals.suggested}</span>
              <span className="caption">ideas offered</span>
            </div>
          </StatCard>
        </BentoItem>
        <BentoItem span={4}>
          <StatCard icon={<Truck size={20} strokeWidth={2} />} title="Delivered">
            <div className="stat-row">
              <span className="stat-big">{totals.ordered}</span>
              <span className="caption">nights off</span>
            </div>
          </StatCard>
        </BentoItem>

        <BentoItem span={6}>
          <div className="card" style={{ padding: 20 }}>
            <SectionHeader eyebrow="Rhythm" title="Cooks per week" />
            <BarList rows={weeks} />
          </div>
        </BentoItem>

        <BentoItem span={6}>
          <div className="card" style={{ padding: 20 }}>
            <SectionHeader eyebrow="Taste" title="Cuisines you cook" />
            <BarList rows={cuisines} />
          </div>
        </BentoItem>

        <BentoItem span={6}>
          <div className="card" style={{ padding: 20 }}>
            <SectionHeader eyebrow="Pantry" title="Most-used ingredients" />
            <BarList rows={ingredients} />
          </div>
        </BentoItem>

        <BentoItem span={6}>
          <div className="card" style={{ padding: 20 }}>
            <SectionHeader eyebrow="Feedback" title="What you tell the chef" />
            <BarList rows={tags} />
          </div>
        </BentoItem>

        {(stats.top_rated || []).length > 0 && (
          <BentoItem span={12}>
            <div className="card" style={{ padding: 20 }}>
              <SectionHeader
                eyebrow="Favorites"
                title="Meals you loved"
                action={<Link to="/history" className="see-all">See history</Link>}
              />
              <div className="ingredients">
                {stats.top_rated.map((m) => (
                  <span key={m.id} className="chip have">
                    <ThumbsUp size={12} strokeWidth={2.4} style={{ verticalAlign: '-2px' }} /> {m.title}
                  </span>
                ))}
              </div>
            </div>
          </BentoItem>
        )}
      </Bento>
    </div>
  )
}
