export default function QueryError({ query, title = "Couldn't load your kitchen" }) {
  return (
    <div className="card narrow" role="alert">
      <h1>{title}</h1>
      <p>Please check your connection and try again.</p>
      <button className="btn primary" onClick={() => query.refetch()} disabled={query.isFetching}>
        {query.isFetching ? 'Reconnecting…' : 'Try again'}
      </button>
    </div>
  )
}
