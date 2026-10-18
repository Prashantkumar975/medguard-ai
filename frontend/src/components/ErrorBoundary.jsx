import { Component } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { AlertTriangle, House, RotateCcw } from 'lucide-react'
import { cx } from './ui'

class Boundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Keep the full detail in the console; the UI shows a friendly page.
    console.error('[MedGuard] Unhandled UI error:', error, info)
  }

  reset = () => this.setState({ error: null })

  render() {
    if (this.state.error) return <ErrorScreen error={this.state.error} onRetry={this.reset} />
    return this.props.children
  }
}

function ErrorScreen({ error, onRetry }) {
  const detail = String(error?.stack || error?.message || error || 'Unknown error')
  return (
    <div role="alert" className="flex min-h-[55vh] flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-4 grid h-12 w-12 place-items-center rounded-full bg-red-50 text-red-600 dark:bg-red-400/10 dark:text-red-300">
        <AlertTriangle size={24} />
      </div>
      <h1 className="font-display text-xl font-bold tracking-tight">Something went wrong</h1>
      <p className="mt-1.5 max-w-md text-sm text-muted">
        An unexpected error stopped this page from loading. Your data is safe — try again, or go back to the dashboard.
      </p>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand px-4 py-2 text-sm font-medium text-on-brand transition-colors hover:bg-brand-dark"
        >
          <RotateCcw size={15} />
          Try again
        </button>
        <Link
          to="/"
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-line bg-surface px-4 py-2 text-sm font-medium transition-colors hover:bg-hover"
        >
          <House size={15} />
          Back to dashboard
        </Link>
      </div>
      <details className="mt-6 w-full max-w-lg text-left">
        <summary className={cx('cursor-pointer select-none text-xs text-muted transition-colors hover:text-ink')}>
          Technical details
        </summary>
        <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap break-words rounded-xl border border-line bg-canvas p-3 font-mono text-[11px] leading-relaxed text-ink/80">
          {detail}
        </pre>
      </details>
    </div>
  )
}

/**
 * Catches render-time errors and shows the custom error page instead of a blank screen.
 * Keyed on the pathname so navigating to another route clears a caught error.
 */
export default function ErrorBoundary({ children }) {
  const { pathname } = useLocation()
  return <Boundary key={pathname}>{children}</Boundary>
}
