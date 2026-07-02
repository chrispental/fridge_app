import { Component } from 'react'

// Catches render errors so a bug shows a recoverable card instead of a blank app.
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="error-boundary">
        <div className="empty">
          <div className="empty-icon">⚠️</div>
          <h3>Something went wrong</h3>
          <p>{this.state.error?.message || 'An unexpected error occurred.'}</p>
          <div style={{ marginTop: 6 }}>
            <button className="btn primary" onClick={() => window.location.reload()}>
              Reload
            </button>
          </div>
        </div>
      </div>
    )
  }
}
