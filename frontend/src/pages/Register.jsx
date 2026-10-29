import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { Building2, Lock, Mail, ShieldCheck, UserRound } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { USE_MOCK } from '../api/client'
import { Button, Card } from '../components/ui'

const inputClass = 'w-full rounded-xl border border-line bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15'

export default function Register() {
  const { register, loading, isAuthenticated } = useAuth()
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [organizationName, setOrganizationName] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!loading && isAuthenticated) return <Navigate to="/" replace />

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (password !== confirmPassword) {
      setError('The passwords do not match.')
      return
    }
    setBusy(true)
    try {
      await register({ name: name.trim(), email: email.trim(), organizationName: organizationName.trim(), password })
      nav('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Account registration failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center py-8">
      <div className="mb-6 text-center">
        <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-brand text-on-brand"><ShieldCheck size={24} /></span>
        <h1 className="mt-4 font-display text-2xl font-bold tracking-tight">Create your workspace</h1>
        <p className="mt-1 text-sm text-muted">Register a new account for MedGuard AI.</p>
      </div>

      <Card>
        <form onSubmit={submit} className="space-y-4 p-5">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">Your name</span>
            <span className="relative block"><UserRound size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input required maxLength={200} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} className={inputClass} placeholder="Full name" /></span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">Email</span>
            <span className="relative block"><Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input required type="email" maxLength={320} autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} placeholder="you@example.org" /></span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">Workspace name</span>
            <span className="relative block"><Building2 size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input required maxLength={200} autoComplete="organization" value={organizationName} onChange={(e) => setOrganizationName(e.target.value)} className={inputClass} placeholder="Research group or organization" /></span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">Password</span>
            <span className="relative block"><Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input required type="password" minLength={12} maxLength={72} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} placeholder="At least 12 characters" /></span>
            <span className="mt-1 block text-xs text-muted">Use at least 12 characters. Passwords are limited to 72 UTF-8 bytes.</span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">Confirm password</span>
            <span className="relative block"><Lock size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" /><input required type="password" minLength={12} maxLength={72} autoComplete="new-password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className={inputClass} placeholder="Enter the password again" /></span>
          </label>

          <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-950">Registration creates a new workspace and makes you its administrator. Email verification is not currently enabled, so use an email address you control.</p>
          {USE_MOCK && <p className="rounded-lg bg-canvas px-3 py-2 text-sm text-muted">Registration is available only when connected to the live API. Switch off demo mode and start the backend.</p>}
          {error && <p role="alert" className="rounded-lg bg-blush px-3 py-2 text-sm text-ink">{error}</p>}
          <Button type="submit" disabled={busy || USE_MOCK} className="w-full justify-center">{busy ? 'Creating account…' : 'Create account'}</Button>
          <p className="text-center text-sm text-muted">Already have an account? <Link to="/login" className="font-medium text-brand hover:underline">Sign in</Link></p>
        </form>
      </Card>
    </div>
  )
}
