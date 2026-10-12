import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client.js'
import { useAuth } from '../auth/useAuth.js'
import { PageHeader, PageSkeleton } from '../components/ui.jsx'

// Approval quantities are the exact stored delta, not the rounded cooking display.
function amount(quantity, unit) {
  if (quantity == null) return `Unknown amount${unit && unit !== 'unknown' ? ` (${unit})` : ''}`
  return `${quantity}${unit && unit !== 'unknown' ? ` ${unit}` : ' (unit unknown)'}`
}

function IngredientList({ title, items, description }) {
  if (!items?.length) return null
  return (
    <section className="card" style={{ padding: 'var(--sp-5)', overflowWrap: 'anywhere' }}>
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      <ul style={{ paddingLeft: '1.25rem' }}>
        {items.map((item, index) => <li key={index}>{item.name}: {amount(item.quantity, item.unit)}</li>)}
      </ul>
    </section>
  )
}

function ApprovalReview({ approvalId }) {
  const { session } = useAuth()
  const queryClient = useQueryClient()
  const queryKey = ['mcp-approvals', session?.user?.id || 'local', approvalId]
  const approval = useQuery({
    queryKey,
    queryFn: ({ signal }) => api.getMcpApproval(approvalId, signal),
    staleTime: 0,
    retry: false,
    refetchInterval: (query) => query.state.data?.status === 'approved'
      && Date.parse(query.state.data.expires_at) > Date.now() ? 3000 : false,
  })
  const [now, setNow] = useState(() => Date.now())
  const inFlight = useRef(false)
  const data = approval.data
  const active = data?.status === 'pending' || data?.status === 'approved'
  const deadline = data?.expires_at ? Date.parse(data.expires_at) : NaN
  const expired = active && (!Number.isFinite(deadline) || now >= deadline)

  useEffect(() => {
    if (!active || expired) return undefined
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [active, expired])

  useEffect(() => {
    if (data?.status === 'consumed') queryClient.invalidateQueries({ queryKey: ['shopping-list'] })
  }, [data?.status, queryClient])

  const decision = useMutation({
    mutationFn: (action) => action === 'approve'
      ? api.approveMcpApproval(approvalId)
      : api.denyMcpApproval(approvalId),
    retry: false,
    meta: { silent: true },
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKey, saved)
      queryClient.invalidateQueries({ queryKey: ['shopping-list'] })
    },
    onError: () => {
      // A dropped response may have committed. Read the receipt; never replay a POST.
      queryClient.invalidateQueries({ queryKey })
    },
  })

  async function decide(action) {
    if (inFlight.current || decision.isPending || decision.isError || approval.isFetching || approval.isError || !active) return
    if (!Number.isFinite(deadline) || Date.now() >= deadline) {
      setNow(Date.now())
      return
    }
    if (action === 'approve' && data.status !== 'pending') return
    inFlight.current = true
    try {
      await queryClient.cancelQueries({ queryKey })
      await decision.mutateAsync(action)
    } catch {
      // The inline error stays visible until a successful explicit status refresh.
    } finally {
      inFlight.current = false
    }
  }

  async function reload() {
    if (inFlight.current || approval.isFetching) return
    const refreshed = await approval.refetch()
    if (!refreshed.isError) decision.reset()
    setNow(Date.now())
  }

  if (approval.isPending) return <PageSkeleton caption="Loading the shopping changes for your review…" />

  if (!data) {
    return (
      <div className="card narrow" style={{ padding: 'var(--sp-5)' }} role="alert">
        <h1>Couldn’t load this approval</h1>
        <p>{approval.error?.status === 404
          ? 'This request is unavailable for your account. Check the link and that you signed in to the right kitchen.'
          : approval.error?.message || 'Check your connection and try again.'}</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <button type="button" className="btn primary" onClick={reload} disabled={approval.isFetching}>Reload approval</button>
          <Link className="btn ghost" to="/shopping">Back to shopping list</Link>
        </div>
      </div>
    )
  }

  const status = expired ? 'expired' : data.status
  const messages = {
    pending: 'Review these exact changes before giving the client permission to add them.',
    approved: 'Approved. Waiting for the client to add these exact items. You can revoke approval until it finishes.',
    consumed: data.already_imported
      ? 'This plan was already imported. No items were added again.'
      : 'These approved changes have been applied to your shopping list.',
    rejected: 'Request declined. The client cannot use this approval.',
    expired: 'This approval has expired. Ask the client to prepare a new preview.',
    stale: 'Your kitchen changed after this preview. Ask the client for a new preview and review it again.',
  }
  const canDecide = active && !expired && !approval.isError && !approval.isFetching && !decision.isPending && !decision.isError
  const changes = data.changes || []
  const expiredAt = Number.isFinite(deadline) ? new Date(deadline).toLocaleString() : 'Unavailable'
  const busy = decision.isPending

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', overflowWrap: 'anywhere' }}>
      <PageHeader
        eyebrow="Client request"
        title="Review shopping changes"
        subtitle="Your approval lets this client add the changes below to your shopping list. Opening this page does not approve anything."
      />
      <section className="card" style={{ padding: 'var(--sp-5)' }} aria-label="Approval details">
        <p><strong>Requesting client:</strong> {data.client_id}</p>
        {session?.user?.email && <p><strong>Your account:</strong> {session.user.email}</p>}
        <p><strong>Plan:</strong> #{data.plan_id}</p>
        {data.meals?.length > 0 && (
          <ul aria-label="Meals in this preview" style={{ paddingLeft: '1.25rem' }}>
            {data.meals.map((meal) => <li key={`${meal.slot_index}-${meal.id}`}>{meal.title}</li>)}
          </ul>
        )}
        <p><strong>Expires:</strong> <time dateTime={data.expires_at}>{expiredAt}</time></p>
        <div className={`banner ${status === 'approved' || status === 'consumed' ? 'success' : 'info'}`} role="status">
          {messages[status] || 'This approval is unavailable. Reload to check its status.'}
        </div>
        {data.already_imported && status !== 'consumed' && <p>This plan has already been imported. It will not be added again.</p>}
      </section>

      <div className="stack" style={{ marginTop: 'var(--sp-5)' }}>
        <section className="card" style={{ padding: 'var(--sp-5)' }} aria-labelledby="shopping-changes-title">
          <h2 id="shopping-changes-title">Exact shopping-list changes ({changes.length})</h2>
          {changes.length === 0 ? <p>No shopping-list changes are proposed.</p> : (
            <ul className="stack" style={{ paddingLeft: '1.25rem', gap: 16 }}>
              {changes.map((change, index) => (
                <li key={index}>
                  <strong>{change.name}</strong>
                  {change.operation === 'create' ? (
                    <p>New item: {amount(change.quantity, change.unit)}</p>
                  ) : (
                    <div>
                      <p>Currently: {amount(change.previous_quantity, change.unit)}</p>
                      <p>Add: {amount(change.added_quantity, change.unit)}</p>
                      <p>After import: {amount(change.quantity, change.unit)}</p>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
        <IngredientList
          title="Check amounts first"
          items={data.check}
          description="These ingredients have uncertain amounts or units. They are excluded from this import. Update your inventory and ask for a new preview if needed."
        />
        <IngredientList title="Already in your kitchen" items={data.have} />
        {data.staples_assumed?.length > 0 && (
          <section className="card" style={{ padding: 'var(--sp-5)' }}>
            <h2>Staples assumed available</h2>
            <p>These staples are excluded from this import: {data.staples_assumed.join(', ')}.</p>
          </section>
        )}
      </div>

      {approval.isError && <div className="banner error" role="alert">Couldn’t refresh this approval. Reload its status before making a decision.</div>}
      {decision.isError && (
        <div className="banner error" role="alert">
          {decision.error.message} Reload the approval status before trying again. Your request may already have been received.
        </div>
      )}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 'var(--sp-5)' }} aria-busy={busy}>
        {status === 'pending' && (
          <button type="button" className="btn primary" onClick={() => decide('approve')} disabled={!canDecide}>
            {busy && decision.variables === 'approve' ? 'Approving…' : 'Approve these changes'}
          </button>
        )}
        {(status === 'pending' || status === 'approved') && (
          <button type="button" className="btn danger" onClick={() => decide('deny')} disabled={!canDecide}>
            {busy && decision.variables === 'deny' ? 'Declining…' : status === 'approved' ? 'Revoke approval' : 'Decline request'}
          </button>
        )}
        <button type="button" className="btn ghost" onClick={reload} disabled={busy || approval.isFetching}>
          {approval.isFetching ? 'Reloading…' : 'Reload approval'}
        </button>
        <Link className="btn ghost" to="/shopping">Back to shopping list</Link>
      </div>
      {busy ? (
        <p className="hint" role="status">Your decision is being sent. Leaving this page will not cancel it.</p>
      ) : status === 'pending' && !decision.isError ? (
        <p className="hint">Leaving this page keeps the request pending. Only Approve these changes grants permission.</p>
      ) : null}
    </div>
  )
}

export default function McpApprovalPage() {
  const { approvalId } = useParams()
  const { authEnabled, session } = useAuth()
  if (!authEnabled || !session) {
    return (
      <div className="card narrow" style={{ padding: 'var(--sp-5)' }}>
        <h1>Shopping approval unavailable</h1>
        <p>Client approvals require a signed-in cloud kitchen with MCP enabled.</p>
        <Link className="btn" to="/shopping">Back to shopping list</Link>
      </div>
    )
  }
  // A newer link must never inherit another request's mutation or error state.
  return <ApprovalReview key={approvalId} approvalId={approvalId} />
}
