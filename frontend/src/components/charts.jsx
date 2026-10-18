import { useEffect, useMemo, useState } from 'react'
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ChartArea, ChartBar, ChartColumn, ChartLine, ChartPie } from 'lucide-react'
import { Card, CardHead, Chip, Segmented, Skeleton, cx } from './ui'
import { VERDICTS } from '../lib/constants'
import { useTheme } from '../theme/ThemeContext'

/* ---------- palette: pale on purpose, and tuned separately for light and dark ---------- */
const LIGHT = {
  changed: '#5fb7a0', flagged: '#e58f88', grid: '#e7ebe8', axis: '#7b847f', ring: '#ffffff',
  verdict: { SUPPORTED: '#7cc7a8', POTENTIAL_CONTRADICTION: '#ec8f89', POSSIBLY_OUTDATED: '#f2c46c', INCOMPLETE_INFORMATION: '#8db4ea', INSUFFICIENT_EVIDENCE: '#b7bdb9' },
}
const DARK = {
  changed: '#5fd0b3', flagged: '#f2a29b', grid: '#262d2a', axis: '#8c978f', ring: '#181d1b',
  verdict: { SUPPORTED: '#6fcfa8', POTENTIAL_CONTRADICTION: '#f09a94', POSSIBLY_OUTDATED: '#efc678', INCOMPLETE_INFORMATION: '#9bbcf0', INSUFFICIENT_EVIDENCE: '#7c8680' },
}
export const useChartColors = () => (useTheme().dark ? DARK : LIGHT)

const SHORT = { SUPPORTED: 'Supported', POTENTIAL_CONTRADICTION: 'Contradiction', POSSIBLY_OUTDATED: 'Outdated', INCOMPLETE_INFORMATION: 'Incomplete', INSUFFICIENT_EVIDENCE: 'Insufficient' }

// Remember the chosen chart mode per chart, across visits.
function useStored(key, initial, allowed) {
  const [v, setV] = useState(() => {
    try { const s = localStorage.getItem(key); return allowed.includes(s) ? s : initial } catch { return initial }
  })
  useEffect(() => { try { localStorage.setItem(key, v) } catch { /* storage blocked */ } }, [key, v])
  return [v, setV]
}

/* ---------- tooltip that matches the rest of the UI ---------- */
function Tip({ active, payload, label, total }) {
  if (!active || !payload?.length) return null
  return (
    <div className="min-w-36 rounded-xl border border-line bg-surface px-3 py-2.5 text-xs shadow-lg shadow-black/10 dark:shadow-black/40">
      {label && <p className="mb-1.5 font-medium text-ink">{label}</p>}
      <ul className="space-y-1">
        {payload.map((p) => (
          <li key={p.dataKey ?? p.name} className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.payload?.fill }} />
            <span className="text-muted">{p.name}</span>
            <span className="ml-auto pl-4 font-medium tabular-nums text-ink">
              {Number(p.value).toLocaleString()}{total ? <span className="ml-1 font-normal text-muted">({Math.round((p.value / total) * 100)}%)</span> : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/* ---------- 1. Scan activity: area / line / bars ---------- */
const ACTIVITY_MODES = [
  { value: 'area', label: 'Area chart', icon: ChartArea },
  { value: 'line', label: 'Line chart', icon: ChartLine },
  { value: 'bar', label: 'Bar chart', icon: ChartColumn },
]

export function ActivityChart({ data }) {
  const c = useChartColors()
  const [mode, setMode] = useStored('mg_chart_activity', 'area', ['area', 'line', 'bar'])
  const [hidden, setHidden] = useState([])
  const toggle = (k) => setHidden((h) => (h.includes(k) ? h.filter((x) => x !== k) : h.length === 1 ? h : [...h, k]))
  const totals = useMemo(() => ({ changed: data?.reduce((s, d) => s + d.changed, 0) ?? 0, flagged: data?.reduce((s, d) => s + d.flagged, 0) ?? 0 }), [data])
  const series = [
    { key: 'changed', name: 'Pages changed', color: c.changed },
    { key: 'flagged', name: 'Findings raised', color: c.flagged },
  ].filter((s) => !hidden.includes(s.key))

  const axis = { tickLine: false, axisLine: false, tick: { fontSize: 11, fill: c.axis } }
  const common = { data, margin: { top: 8, right: 12, left: -16, bottom: 0 } }
  const grid = <CartesianGrid vertical={false} stroke={c.grid} strokeDasharray="3 4" />
  const xy = (<><XAxis dataKey="day" {...axis} interval={1} tickMargin={8} /><YAxis {...axis} allowDecimals={false} width={44} tickMargin={4} /></>)
  const dot = (color) => ({ r: 5, fill: color, stroke: c.ring, strokeWidth: 2 })

  return (
    <Card>
      <CardHead title="Changes found and findings raised" hint="Last 14 days across all monitored websites" action={<Segmented label="Chart type" value={mode} onChange={setMode} options={ACTIVITY_MODES} />} />
      <div className="flex flex-wrap gap-2 px-5 pb-2">
        <Chip on={!hidden.includes('changed')} color={c.changed} onClick={() => toggle('changed')}>Pages changed <span className="tabular-nums text-muted">{totals.changed}</span></Chip>
        <Chip on={!hidden.includes('flagged')} color={c.flagged} onClick={() => toggle('flagged')}>Findings raised <span className="tabular-nums text-muted">{totals.flagged}</span></Chip>
      </div>
      <div className="h-64 px-2 pb-3" role="img" aria-label={`${ACTIVITY_MODES.find((m) => m.value === mode).label} of pages changed and findings raised per day for the last 14 days. ${totals.changed} pages changed and ${totals.flagged} findings raised in total.`}>
        {data ? (
          <ResponsiveContainer>
            {mode === 'bar' ? (
              <BarChart {...common} barGap={4} barCategoryGap="28%">
                {grid}{xy}
                <Tooltip content={<Tip />} cursor={{ fill: c.grid, opacity: 0.55, radius: 8 }} />
                {series.map((s) => <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[6, 6, 2, 2]} maxBarSize={18} />)}
              </BarChart>
            ) : mode === 'line' ? (
              <LineChart {...common}>
                {grid}{xy}
                <Tooltip content={<Tip />} cursor={{ stroke: c.axis, strokeOpacity: 0.4, strokeDasharray: '3 3' }} />
                {series.map((s) => <Line key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2.5} dot={false} activeDot={dot(s.color)} />)}
              </LineChart>
            ) : (
              <AreaChart {...common}>
                <defs>
                  {['changed', 'flagged'].map((k) => (
                    <linearGradient key={k} id={`ga-${k}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={c[k]} stopOpacity={0.38} /><stop offset="100%" stopColor={c[k]} stopOpacity={0.02} />
                    </linearGradient>
                  ))}
                </defs>
                {grid}{xy}
                <Tooltip content={<Tip />} cursor={{ stroke: c.axis, strokeOpacity: 0.4, strokeDasharray: '3 3' }} />
                {series.map((s) => <Area key={s.key} type="monotone" dataKey={s.key} name={s.name} stroke={s.color} strokeWidth={2.5} fill={`url(#ga-${s.key})`} activeDot={dot(s.color)} />)}
              </AreaChart>
            )}
          </ResponsiveContainer>
        ) : <Skeleton className="m-3 h-full" />}
      </div>
    </Card>
  )
}

/* ---------- 2. Claim verdicts: bars / donut / columns ---------- */
const VERDICT_MODES = [
  { value: 'bars', label: 'Horizontal bars', icon: ChartBar },
  { value: 'donut', label: 'Donut chart', icon: ChartPie },
  { value: 'columns', label: 'Column chart', icon: ChartColumn },
]

export function VerdictChart({ data }) {
  const c = useChartColors()
  const [mode, setMode] = useStored('mg_chart_verdict', 'bars', ['bars', 'donut', 'columns'])
  // Supported claims outnumber the rest ~300 to 1, so they hide everything else. Off by default.
  const [withSupported, setWithSupported] = useState(false)

  const all = data ?? []
  const totalAll = all.reduce((s, v) => s + v.count, 0)
  const supported = all.find((v) => v.verdict === 'SUPPORTED')?.count ?? 0
  const rows = useMemo(
    () => all.filter((v) => withSupported || v.verdict !== 'SUPPORTED').map((v) => ({ ...v, name: VERDICTS[v.verdict].label, short: SHORT[v.verdict], fill: c.verdict[v.verdict] })),
    [all, withSupported, c]
  )
  const total = rows.reduce((s, r) => s + r.count, 0)
  const max = Math.max(1, ...rows.map((r) => r.count))
  const flaggedTotal = totalAll - supported
  const pctSupported = totalAll ? ((supported / totalAll) * 100).toFixed(1) : '0'

  return (
    <Card>
      <CardHead title="How claims were assessed" hint="All verified claims" action={<Segmented label="Chart type" value={mode} onChange={setMode} options={VERDICT_MODES} />} />
      {!data ? <div className="px-5 pb-5"><Skeleton className="h-52" /></div> : (
        <div className="px-5 pb-5">
          <div className="flex items-center justify-between gap-3 rounded-xl bg-mint px-3.5 py-2.5">
            <p className="text-sm text-ink"><span className="font-display text-lg font-bold">{pctSupported}%</span> <span className="text-ink/75">supported by official sources</span></p>
            <p className="text-xs text-ink/65">{flaggedTotal} flagged</p>
          </div>
          <div className="mt-3 flex justify-end">
            <Chip on={withSupported} onClick={() => setWithSupported((v) => !v)}>Include supported</Chip>
          </div>

          <div className="mt-2" role="img" aria-label={`Claims by verdict: ${rows.map((r) => `${r.name} ${r.count}`).join(', ')}`}>
            {mode === 'bars' && (
              <ul className="space-y-3">
                {rows.map((r) => (
                  <li key={r.verdict}>
                    <div className="mb-1 flex items-baseline justify-between text-sm">
                      <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: r.fill }} />{r.name}</span>
                      <span className="tabular-nums"><span className="font-medium">{r.count.toLocaleString()}</span> <span className="text-xs text-muted">{Math.round((r.count / total) * 100)}%</span></span>
                    </div>
                    <div className="h-2.5 rounded-full bg-track"><div className="h-2.5 rounded-full transition-all duration-500" style={{ width: `${Math.max(3, (r.count / max) * 100)}%`, background: r.fill }} /></div>
                  </li>
                ))}
              </ul>
            )}

            {mode === 'donut' && (
              <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-3 sm:flex-nowrap">
                <div className="relative h-44 w-44 shrink-0">
                  <ResponsiveContainer>
                    <PieChart>
                      <Tooltip content={<Tip total={total} />} />
                      <Pie data={rows} dataKey="count" nameKey="name" innerRadius={56} outerRadius={80} paddingAngle={3} cornerRadius={6} stroke="none" startAngle={90} endAngle={-270}>
                        {rows.map((r) => <Cell key={r.verdict} fill={r.fill} />)}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="pointer-events-none absolute inset-0 grid place-content-center text-center">
                    <p className="font-display text-2xl font-bold leading-none tabular-nums">{total.toLocaleString()}</p>
                    <p className="mt-1 text-xs text-muted">{withSupported ? 'claims' : 'flagged'}</p>
                  </div>
                </div>
                <ul className="min-w-0 flex-1 space-y-2 text-sm">
                  {rows.map((r) => (
                    <li key={r.verdict} className="flex items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: r.fill }} /><span className="truncate">{r.short}</span><span className="ml-auto pl-2 font-medium tabular-nums">{r.count.toLocaleString()}</span></li>
                  ))}
                </ul>
              </div>
            )}

            {mode === 'columns' && (
              <div className="h-52">
                <ResponsiveContainer>
                  <BarChart data={rows} margin={{ top: 8, right: 4, left: -22, bottom: 0 }} barCategoryGap="22%">
                    <CartesianGrid vertical={false} stroke={c.grid} strokeDasharray="3 4" />
                    <XAxis dataKey="short" tickLine={false} axisLine={false} tick={{ fontSize: 10.5, fill: c.axis }} tickMargin={8} interval={0} />
                    <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: c.axis }} allowDecimals={false} />
                    <Tooltip content={<Tip total={total} />} cursor={{ fill: c.grid, opacity: 0.55, radius: 8 }} />
                    <Bar dataKey="count" name="Claims" radius={[8, 8, 3, 3]} maxBarSize={38}>
                      {rows.map((r) => <Cell key={r.verdict} fill={r.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}
