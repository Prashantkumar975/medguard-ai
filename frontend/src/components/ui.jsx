import { createContext, useCallback, useContext, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, Check, ChevronDown, Inbox, X } from 'lucide-react'
import { PRIORITIES, STATUSES, VERDICTS } from '../lib/constants'

export const cx = (...a) => a.filter(Boolean).join(' ')

export const Card = ({ className, children, ...p }) => (
  <div className={cx('rounded-2xl border border-line bg-surface', className)} {...p}>{children}</div>
)

export const CardHead = ({ title, hint, action }) => (
  <div className="flex flex-wrap items-start justify-between gap-3 px-5 pb-3 pt-4">
    <div>
      <h3 className="font-display text-[15px] font-bold tracking-tight">{title}</h3>
      {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
    </div>
    {action}
  </div>
)

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-[28px] font-bold leading-tight tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  )
}

const BTN = {
  primary: 'bg-ink text-on-ink hover:bg-ink/80',
  brand: 'bg-brand text-on-brand hover:bg-brand-dark',
  outline: 'border border-line bg-surface hover:bg-hover',
  ghost: 'hover:bg-ink/5',
  danger: 'bg-red-600 text-white hover:bg-red-700',
}
export const Button = ({ variant = 'primary', size = 'md', className, ...p }) => (
  <button
    {...p}
    className={cx(
      'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
      size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm',
      BTN[variant], className
    )}
  />
)

const TONES = {
  green: ['bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-400/10 dark:text-emerald-200 dark:ring-emerald-300/20', 'bg-emerald-400'],
  red: ['bg-rose-50 text-rose-800 ring-rose-200 dark:bg-rose-400/10 dark:text-rose-200 dark:ring-rose-300/20', 'bg-rose-400'],
  amber: ['bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-300/10 dark:text-amber-200 dark:ring-amber-200/20', 'bg-amber-300'],
  orange: ['bg-orange-50 text-orange-800 ring-orange-200 dark:bg-orange-300/10 dark:text-orange-200 dark:ring-orange-200/20', 'bg-orange-300'],
  blue: ['bg-sky-50 text-sky-800 ring-sky-200 dark:bg-sky-400/10 dark:text-sky-200 dark:ring-sky-300/20', 'bg-sky-400'],
  violet: ['bg-violet-50 text-violet-800 ring-violet-200 dark:bg-violet-400/10 dark:text-violet-200 dark:ring-violet-300/20', 'bg-violet-400'],
  slate: ['bg-stone-100 text-stone-700 ring-stone-200 dark:bg-white/5 dark:text-stone-300 dark:ring-white/10', 'bg-stone-400'],
}
export const Pill = ({ tone = 'slate', children, className }) => (
  <span className={cx('inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset', TONES[tone][0], className)}>
    <span className={cx('h-1.5 w-1.5 rounded-full', TONES[tone][1])} />
    {children}
  </span>
)
export const PriorityBadge = ({ value }) => <Pill tone={PRIORITIES[value]?.tone}>{PRIORITIES[value]?.label ?? value}</Pill>
export const VerdictBadge = ({ value }) => <Pill tone={VERDICTS[value]?.tone}>{VERDICTS[value]?.label ?? value}</Pill>
export const StatusBadge = ({ value }) => <Pill tone={STATUSES[value]?.tone}>{STATUSES[value]?.label ?? value}</Pill>
export const toneDot = (t) => TONES[t ?? 'slate'][1]
export const verdictDot = (v) => TONES[VERDICTS[v]?.tone ?? 'slate'][1]

export function Spark({ data, className, w = 84, h = 32 }) {
  const max = Math.max(...data), min = Math.min(...data), r = max - min || 1
  const step = w / data.length
  return (
    <svg width={w} height={h} aria-hidden="true" className={className}>
      {data.map((v, i) => {
        const bh = Math.max(4, ((v - min) / r) * (h - 6) + 4)
        return <rect key={i} x={i * step} y={h - bh} width={step - 3} height={bh} rx="2.5" fill="currentColor" opacity={i === data.length - 1 ? 1 : 0.32} />
      })}
    </svg>
  )
}

export const Skeleton = ({ className }) => <div className={cx('animate-pulse rounded-lg bg-ink/[0.07]', className)} />

export const Empty = ({ title, hint, children }) => (
  <div className="flex flex-col items-center px-6 py-14 text-center">
    <div className="mb-3 grid h-11 w-11 place-items-center rounded-full bg-brand-soft text-brand"><Inbox size={20} /></div>
    <p className="font-display text-base font-bold">{title}</p>
    {hint && <p className="mt-1 max-w-sm text-sm text-muted">{hint}</p>}
    {children && <div className="mt-4">{children}</div>}
  </div>
)

export const ErrorState = ({ error, onRetry }) => (
  <div className="flex flex-col items-center px-6 py-12 text-center">
    <div className="mb-3 grid h-11 w-11 place-items-center rounded-full bg-red-50 text-red-600 dark:bg-red-400/10 dark:text-red-300"><AlertTriangle size={20} /></div>
    <p className="font-display text-base font-bold">Couldn't load this data</p>
    <p className="mt-1 max-w-sm text-sm text-muted">{error?.message || 'Something went wrong.'}</p>
    {onRetry && <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>Try again</Button>}
  </div>
)

export const Banner = ({ tone = 'blue', children, onClose }) => (
  <div className={cx('mb-4 flex items-start justify-between gap-3 rounded-xl px-4 py-3 text-sm ring-1 ring-inset', TONES[tone][0])}>
    <div className="min-w-0">{children}</div>
    {onClose && <button onClick={onClose} aria-label="Dismiss"><X size={16} /></button>}
  </div>
)

export function Modal({ title, onClose, children }) {
  useEffect(() => {
    const h = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/30 p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-label={title} className="w-full max-w-md rounded-2xl bg-surface p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-lg font-bold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 hover:bg-ink/5"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

export const Toggle = ({ checked, onChange, disabled, label }) => (
  <button
    role="switch" aria-checked={checked} aria-label={label} disabled={disabled} onClick={() => onChange(!checked)}
    className={cx('relative h-6 w-11 shrink-0 rounded-full transition-colors duration-150 disabled:opacity-50', checked ? 'bg-brand' : 'bg-toggle')}
  >
    <span className={cx('absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-transform duration-150', checked ? 'translate-x-[20px]' : 'translate-x-0')} />
  </button>
)

export const inputCls = 'w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/15 disabled:bg-hover'
export const Field = ({ label, hint, children }) => (
  <label className="block">
    <span className="mb-1.5 block text-sm font-medium">{label}</span>
    {children}
    {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
  </label>
)

export function Highlight({ text, offsets, kind = 'claim' }) {
  if (!offsets || offsets[0] < 0) return <>{text}</>
  const [s, e] = offsets
  return <>{text.slice(0, s)}<mark className={`hl-${kind}`}>{text.slice(s, e)}</mark>{text.slice(e)}</>
}

const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)
export function ToastProvider({ children }) {
  const [items, setItems] = useState([])
  const push = useCallback((message, tone = 'green') => {
    const id = Math.random().toString(36).slice(2)
    setItems((l) => [...l, { id, message, tone }])
    setTimeout(() => setItems((l) => l.filter((t) => t.id !== id)), 4000)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div aria-live="polite" className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2">
        {items.map((t) => (
          <div key={t.id} className={cx('rounded-xl px-4 py-3 text-sm font-medium shadow-lg ring-1 ring-inset', TONES[t.tone][0])}>{t.message}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

/* ---------- Segmented control (chart modes, theme) ---------- */
export function Segmented({ value, onChange, options, label, size = 'md', className }) {
  const refs = useRef([])
  const move = (e, i) => {
    const d = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0
    if (!d) return
    e.preventDefault()
    const n = (i + d + options.length) % options.length
    onChange(options[n].value)
    refs.current[n]?.focus()
  }
  return (
    <div role="radiogroup" aria-label={label} className={cx('inline-flex gap-0.5 rounded-xl bg-track p-0.5', className)}>
      {options.map((o, i) => {
        const on = o.value === value
        const Icon = o.icon
        return (
          <button
            key={o.value} ref={(el) => (refs.current[i] = el)} type="button" role="radio" aria-checked={on} aria-label={o.label} title={o.label}
            tabIndex={on ? 0 : -1} onClick={() => onChange(o.value)} onKeyDown={(e) => move(e, i)}
            className={cx(
              'inline-flex items-center justify-center gap-1.5 rounded-[10px] font-medium transition-colors',
              size === 'sm' ? 'h-7 px-2 text-xs' : 'h-8 px-2.5 text-xs',
              on ? 'bg-surface text-ink shadow-sm ring-1 ring-line' : 'text-muted hover:text-ink'
            )}
          >
            {Icon && <Icon size={15} aria-hidden="true" />}
            {o.text && <span>{o.text}</span>}
          </button>
        )
      })}
    </div>
  )
}

/* ---------- Select: replaces the native <select> everywhere ---------- */
// options: [{ value, label, hint?, dot? }]. onChange receives the value, not an event.
export function Select({ value, onChange, options, ariaLabel, placeholder = 'Select', disabled, className, align = 'left', block }) {
  const id = useId()
  const btn = useRef(null)
  const list = useRef(null)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [pos, setPos] = useState(null)
  const typed = useRef({ s: '', t: 0 })

  const idx = options.findIndex((o) => o.value === value)
  const current = options[idx]

  const place = useCallback(() => {
    const r = btn.current?.getBoundingClientRect()
    if (!r) return
    const h = Math.min(288, options.length * 40 + 12)
    const up = window.innerHeight - r.bottom < h + 12 && r.top > h + 12
    setPos({ left: r.left, right: window.innerWidth - r.right, width: r.width, top: up ? undefined : r.bottom + 6, bottom: up ? window.innerHeight - r.top + 6 : undefined })
  }, [options.length])

  useLayoutEffect(() => { if (open) place() }, [open, place])
  useEffect(() => {
    if (!open) return
    const out = (e) => { if (!btn.current?.contains(e.target) && !list.current?.contains(e.target)) setOpen(false) }
    const close = (e) => { if (!list.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', out)
    window.addEventListener('resize', place)
    window.addEventListener('scroll', close, true)
    return () => { document.removeEventListener('mousedown', out); window.removeEventListener('resize', place); window.removeEventListener('scroll', close, true) }
  }, [open, place])
  useEffect(() => { if (open) list.current?.querySelector(`[data-i="${active}"]`)?.scrollIntoView({ block: 'nearest' }) }, [active, open])

  const show = () => { setActive(Math.max(0, idx)); setOpen(true) }
  const pick = (i) => { const o = options[i]; if (o) onChange(o.value); setOpen(false); btn.current?.focus() }

  const onKey = (e) => {
    const k = e.key
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(k)) { e.preventDefault(); show() }
      return
    }
    if (k === 'Escape') { e.preventDefault(); e.stopPropagation(); setOpen(false) }
    else if (k === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(options.length - 1, a + 1)) }
    else if (k === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(0, a - 1)) }
    else if (k === 'Home') { e.preventDefault(); setActive(0) }
    else if (k === 'End') { e.preventDefault(); setActive(options.length - 1) }
    else if (k === 'Enter' || k === ' ') { e.preventDefault(); pick(active) }
    else if (k === 'Tab') setOpen(false)
    else if (k.length === 1) {
      const t = typed.current, now = Date.now()
      t.s = now - t.t > 600 ? k.toLowerCase() : t.s + k.toLowerCase(); t.t = now
      const n = options.findIndex((o) => o.label.toLowerCase().startsWith(t.s))
      if (n >= 0) setActive(n)
    }
  }

  return (
    <>
      <button
        ref={btn} type="button" role="combobox" aria-haspopup="listbox" aria-expanded={open} aria-controls={`${id}-list`} aria-label={ariaLabel}
        aria-activedescendant={open ? `${id}-${active}` : undefined} disabled={disabled}
        onClick={() => (open ? setOpen(false) : show())} onKeyDown={onKey}
        className={cx(
          'flex items-center justify-between gap-2 rounded-xl border bg-surface px-3 py-2 text-left text-sm outline-none transition',
          'hover:bg-hover focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-50',
          open ? 'border-brand ring-2 ring-brand/20' : 'border-line',
          block !== false && 'w-full', className
        )}
      >
        <span className={cx('flex min-w-0 items-center gap-2', !current && 'text-muted')}>
          {current?.dot && <span className={cx('h-2 w-2 shrink-0 rounded-full', current.dot)} />}
          <span className="truncate">{current?.label ?? placeholder}</span>
        </span>
        <ChevronDown size={16} aria-hidden="true" className={cx('shrink-0 text-muted transition-transform', open && 'rotate-180')} />
      </button>
      {open && pos && createPortal(
        <ul
          ref={list} id={`${id}-list`} role="listbox" aria-label={ariaLabel}
          onMouseDown={(e) => e.preventDefault()} onClick={(e) => e.stopPropagation()}
          style={{ position: 'fixed', top: pos.top, bottom: pos.bottom, ...(align === 'right' ? { right: pos.right } : { left: pos.left }), minWidth: Math.max(pos.width, 176) }}
          className="mg-pop z-[90] max-h-72 overflow-y-auto rounded-xl border border-line bg-surface p-1.5 shadow-xl shadow-black/10 dark:shadow-black/40"
        >
          {options.map((o, i) => {
            const sel = o.value === value
            return (
              <li
                key={String(o.value)} id={`${id}-${i}`} data-i={i} role="option" aria-selected={sel}
                onMouseEnter={() => setActive(i)} onClick={() => pick(i)}
                className={cx('flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm', i === active ? 'bg-brand-soft' : '', sel && 'font-medium')}
              >
                {o.dot && <span className={cx('h-2 w-2 shrink-0 rounded-full', o.dot)} />}
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{o.label}</span>
                  {o.hint && <span className="block truncate text-xs font-normal text-muted">{o.hint}</span>}
                </span>
                {sel && <Check size={15} aria-hidden="true" className="shrink-0 text-brand" />}
              </li>
            )
          })}
        </ul>,
        document.body
      )}
    </>
  )
}

/* ---------- Small on/off chip (chart series, "include supported") ---------- */
export const Chip = ({ on, onClick, color, children, className }) => (
  <button
    type="button" aria-pressed={on} onClick={onClick}
    className={cx(
      'inline-flex select-none items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
      on ? 'border-brand bg-brand-soft text-ink ring-1 ring-brand/30' : 'border-dashed border-line text-muted hover:border-solid hover:text-ink',
      className
    )}
  >
    {color ? <span className="h-2 w-2 rounded-full transition-opacity" style={{ background: color, opacity: on ? 1 : 0.3 }} />
      : <span className={cx('grid h-3.5 w-3.5 place-items-center rounded-full border transition-colors', on ? 'border-brand bg-brand text-on-brand' : 'border-line')}>{on && <Check size={10} strokeWidth={3} aria-hidden="true" />}</span>}
    {children}
  </button>
)
