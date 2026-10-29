import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ShieldCheck, Lock, Mail } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { USE_MOCK } from '../api/client'
import { Card, Button } from '../components/ui'

// In demo mode any non-empty credentials start a clearly labeled sample session.
export default function Login() {
  const { login, loading, isAuthenticated } = useAuth()
  const nav = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [organizationId, setOrganizationId] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  if (!loading && isAuthenticated) {
    const from = location.state?.from?.pathname || '/'
    return <Navigate to={from} replace />
  }

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      await login(email.trim(), password, organizationId.trim())
      nav(location.state?.from?.pathname || '/', { replace: true })
    } catch (ex) {
      setErr(ex.message || 'Sign-in failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center">
      <div className="mb-6 text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-brand text-on-brand">
          <ShieldCheck size={24} />
        </span>
        <h1 className="mt-4 font-display text-2xl font-bold tracking-tight">Sign in to MedGuard AI</h1>
        <p className="mt-1 text-sm text-muted">Clinical review requires an authorized account.</p>
        {USE_MOCK && <p className="mt-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950">Demo mode: enter any email and password to open the sample workspace. This does not authenticate with a real account.</p>}
      </div>
      <Card>
        <form onSubmit={submit} className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">Email</span>
            <span className="relative block">
              <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                type="email" required autoComplete="email" value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-line bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
                placeholder="you@medguard.example"
              />
            </span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">Password</span>
            <span className="relative block">
              <Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                type="password" required autoComplete="current-password" value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-line bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
                placeholder="••••••••"
              />
            </span>
          </label>
          {!USE_MOCK && (
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium">Organization ID <span className="font-normal text-muted">(if required)</span></span>
              <input
                type="text" autoComplete="organization" value={organizationId}
                onChange={(e) => setOrganizationId(e.target.value)}
                className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15"
                placeholder="Provided by your administrator"
              />
            </label>
          )}
          {err && <p className="rounded-lg bg-blush px-3 py-2 text-sm text-ink">{err}</p>}
          <Button type="submit" disabled={busy} className="w-full justify-center">
            {busy ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>
        {!USE_MOCK && <p className="mt-4 border-t border-line pt-4 text-center text-sm text-muted">New to MedGuard AI? <Link to="/register" className="font-medium text-brand hover:underline">Create an account</Link></p>}
      </Card>
    </div>
  )
}
