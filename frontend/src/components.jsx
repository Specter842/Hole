import React, { useState, useEffect, useRef } from 'react'
import { ChevronDown, MoreHorizontal, ArrowLeft } from 'lucide-react'
import { C } from './tokens.js'

// A detail page reached by clicking into a list (job, application) has no
// other affordance back to it -- this app navigates with real page loads,
// not client-side routing, so there's no breadcrumb trail to lean on.
export function BackLink({ href, label }) {
  return (
    <a
      href={href}
      className="link-lime focus-ring inline-flex items-center gap-1.5 text-xs font-medium mb-6"
      style={{ color: C.lime }}
    >
      <ArrowLeft size={14} /> {label}
    </a>
  )
}

export function PageHeader({ title, subtitle }) {
  return (
    <div className="mb-8">
      <h1 className="text-3xl md:text-4xl font-bold tracking-tight" style={{ color: C.text }}>
        {title}
      </h1>
      {subtitle && (
        <p className="mt-2 text-sm max-w-2xl" style={{ color: C.textSub }}>
          {subtitle}
        </p>
      )}
    </div>
  )
}

export function DeltaChip({ delta }) {
  if (delta === undefined || delta === null) return null
  const positive = delta >= 0
  return (
    <span
      className="inline-flex items-center gap-1 text-[11px] font-semibold px-1.5 py-0.5 rounded-md"
      style={{
        color: positive ? C.lime : C.red,
        background: positive ? C.limeDim : 'rgba(255,90,90,.14)',
      }}
    >
      {positive ? '↑' : '↓'} {Math.abs(delta).toFixed(2)}%
    </span>
  )
}

export function MoreDots() {
  return (
    <span className="text-sm leading-none select-none" style={{ color: C.textMute }} aria-hidden="true">
      &#8942;
    </span>
  )
}

// Icon badge colors cycle through the chart palette so a row of stat cards
// reads as a set the way the reference's does, rather than every icon
// competing for the same accent.
const BADGE_TONES = [
  { bg: C.limeDim, fg: C.lime },
  { bg: C.purpleDim, fg: C.purple },
  { bg: 'rgba(61,224,214,.14)', fg: C.teal },
  { bg: 'rgba(255,210,61,.14)', fg: C.yellow },
  { bg: 'rgba(255,110,199,.14)', fg: C.pink },
]

export function MetricCard({ label, value, delta, icon: Icon, tone = 0 }) {
  const badge = BADGE_TONES[tone % BADGE_TONES.length]
  return (
    <div
      className="dash-card rounded-2xl p-5"
      style={{ background: C.panel, border: `1px solid ${C.border}` }}
    >
      <div className="flex items-start justify-between">
        {Icon ? (
          <span
            className="h-9 w-9 rounded-xl flex items-center justify-center"
            style={{ background: badge.bg, color: badge.fg }}
          >
            <Icon size={17} strokeWidth={2.25} />
          </span>
        ) : (
          <span />
        )}
        <MoreDots />
      </div>
      <div className="mt-3 text-2xl font-bold tracking-tight" style={{ color: C.text }}>
        {value}
      </div>
      <div className="mt-1 flex items-center gap-2">
        <span className="text-xs" style={{ color: C.textMute }}>
          {label}
        </span>
        <DeltaChip delta={delta} />
      </div>
    </div>
  )
}

export function Panel({ title, children, className = '', menu = true, variant = 'label' }) {
  return (
    <div
      className={`dash-card rounded-2xl p-5 ${className}`}
      style={{ background: C.panel, border: `1px solid ${C.border}` }}
    >
      {title && (
        <div className="flex items-center justify-between mb-5">
          <div
            className={
              variant === 'header'
                ? 'text-sm font-semibold'
                : 'text-xs font-semibold uppercase tracking-wide'
            }
            style={{ color: variant === 'header' ? C.text : C.textSub }}
          >
            {title}
          </div>
          {menu && <MoreDots />}
        </div>
      )}
      {children}
    </div>
  )
}

export function Empty({ children = 'Nothing here yet.' }) {
  return (
    <div className="text-sm py-10 text-center" style={{ color: C.textMute }}>
      {children}
    </div>
  )
}

// Same tone vocabulary as DashboardPage's TONE_COLOR / STATUS_TONE in
// jobsearch/web/pages.py. Three distinct colors on purpose: lime is the
// primary accent everywhere else on the page, so reusing it for "warn" would
// make a caution pill read as an active/positive one.
const TONE_COLOR = {
  bad: C.red,
  warn: C.yellow,
  good: C.lime,
  '': C.textSub,
}

export function StatusPill({ label, tone = '' }) {
  if (!label) return null
  return (
    <span
      className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide px-2 py-1 rounded-full whitespace-nowrap"
      style={{ background: C.panelAlt, border: `1px solid ${C.border}`, color: TONE_COLOR[tone] || C.textSub }}
    >
      {label}
    </span>
  )
}

export function ScoreBar({ score }) {
  if (score === null || score === undefined) {
    return <span style={{ color: C.textMute }}>&mdash;</span>
  }
  const pct = Math.max(0, Math.min(100, Number(score)))
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-mono tabular-nums" style={{ color: C.textSub }}>{pct.toFixed(1)}</span>
      <span className="inline-block h-[3px] w-24 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,.1)' }}>
        <span className="block h-full" style={{ width: `${pct}%`, background: C.lime }} />
      </span>
    </div>
  )
}

// A plain table for row/column data -- `columns` is [{key, label}], `rows`
// is an array of plain objects; a cell may be any renderable node.
export function DataTable({ columns, rows, empty = 'Nothing here yet.', rowKey }) {
  if (!rows || !rows.length) return <Empty>{empty}</Empty>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className="text-left font-semibold uppercase tracking-wide text-[11px] pb-3 pr-4"
                style={{ color: C.textMute, borderBottom: `1px solid ${C.border}` }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={rowKey ? rowKey(row) : i} className="data-row">
              {columns.map((col) => (
                <td
                  key={col.key}
                  className="py-3.5 pr-4 align-top"
                  style={{ borderBottom: `1px solid ${C.border}`, color: C.textSub }}
                >
                  {col.render ? col.render(row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function KV({ items }) {
  const shown = (items || []).filter((it) => it.value !== '' && it.value !== null && it.value !== undefined)
  if (!shown.length) return null
  return (
    <dl className="grid gap-3 text-sm">
      {shown.map((it) => (
        <div key={it.label} className="grid gap-3 items-start" style={{ gridTemplateColumns: '160px 1fr' }}>
          <dt className="text-[11px] font-semibold uppercase tracking-wide pt-0.5" style={{ color: C.textMute }}>
            {it.label}
          </dt>
          <dd className="m-0" style={{ color: C.text }}>{it.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function NoticeBlock({ tone = '', text, items = [] }) {
  return (
    <div
      className="rounded-xl p-4 text-sm mb-6"
      style={{ background: 'rgba(255,255,255,.03)', border: `1px solid ${TONE_COLOR[tone] || C.border}`, color: C.textSub }}
    >
      <div className="font-semibold mb-1" style={{ color: TONE_COLOR[tone] || C.text }}>{text}</div>
      {items.length > 0 && (
        <ul className="list-disc pl-5 mt-1 space-y-0.5">
          {items.map((item, i) => <li key={i}>{item}</li>)}
        </ul>
      )}
    </div>
  )
}

const inputStyle = {
  background: 'rgba(255,255,255,.04)',
  border: `1px solid ${C.border}`,
  color: C.text,
}

export function TextField({ name, label, defaultValue = '', type = 'text', placeholder = '', hint = '', hidden }) {
  if (hidden) return <input type="hidden" name={name} defaultValue={defaultValue} />
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      {label && <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: C.textSub }}>{label}</span>}
      <input
        type={type}
        name={name}
        defaultValue={defaultValue}
        placeholder={placeholder}
        className="rounded-lg px-3 py-2.5 text-sm focus-ring"
        style={inputStyle}
      />
      {hint && <span className="text-xs" style={{ color: C.textMute }}>{hint}</span>}
    </label>
  )
}

export function TextAreaField({ name, label, defaultValue = '', placeholder = '', hint = '', rows = 3 }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      {label && <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: C.textSub }}>{label}</span>}
      <textarea
        name={name}
        defaultValue={defaultValue}
        placeholder={placeholder}
        rows={rows}
        className="rounded-lg px-3 py-2.5 text-sm focus-ring"
        style={inputStyle}
      />
      {hint && <span className="text-xs" style={{ color: C.textMute }}>{hint}</span>}
    </label>
  )
}

export function SelectField({ name, label, defaultValue = '', options = [] }) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      {label && <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: C.textSub }}>{label}</span>}
      <select name={name} defaultValue={defaultValue} className="rounded-lg px-3 py-2.5 text-sm focus-ring" style={inputStyle}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  )
}

// A real POST form carrying the session token -- jobsearch/web/server.py's
// App.post() rejects any mutating request whose `token` field doesn't match
// the one minted at startup, so every form here must keep sending it. Real
// <form method="post"> submission (no client fetch/state) is deliberate: it
// is the lowest-risk way to port a mutation path, per this port's own rule.
export function PostForm({ action, token, children, submitLabel = 'Save', inline = false, confirm = '' }) {
  const onSubmit = confirm
    ? (e) => { if (!window.confirm(confirm)) e.preventDefault() }
    : undefined
  return (
    <form method="post" action={action} onSubmit={onSubmit} className={inline ? 'inline' : 'flex flex-col gap-4'}>
      <input type="hidden" name="token" defaultValue={token} />
      {children}
      <div className={inline ? 'inline' : 'flex gap-3 pt-1'}>
        <button
          type="submit"
          className="text-xs font-semibold uppercase tracking-wide px-4 py-2.5 rounded-lg focus-ring"
          style={{ background: C.lime, color: C.onLime }}
        >
          {submitLabel}
        </button>
      </div>
    </form>
  )
}

export function DeleteButton({ action, token, label = 'Delete', confirm = '' }) {
  const onSubmit = confirm ? (e) => { if (!window.confirm(confirm)) e.preventDefault() } : undefined
  return (
    <form method="post" action={action} onSubmit={onSubmit} className="inline">
      <input type="hidden" name="token" defaultValue={token} />
      <button
        type="submit"
        className="text-[11px] font-medium uppercase tracking-wide px-2.5 py-1.5 rounded-md focus-ring"
        style={{ color: C.textMute, border: `1px solid ${C.border}` }}
      >
        {label}
      </button>
    </form>
  )
}

export function ActionButton({ action, token, label, confirm = '', primary = false }) {
  const onSubmit = confirm ? (e) => { if (!window.confirm(confirm)) e.preventDefault() } : undefined
  return (
    <form method="post" action={action} onSubmit={onSubmit} className="inline">
      <input type="hidden" name="token" defaultValue={token} />
      <button
        type="submit"
        className="text-xs font-semibold uppercase tracking-wide px-4 py-2.5 rounded-lg focus-ring"
        style={primary ? { background: C.lime, color: C.onLime } : { color: C.text, border: `1px solid ${C.border}` }}
      >
        {label}
      </button>
    </form>
  )
}

export function useToast() {
  const [msg, setMsg] = useState(null)
  const timer = useRef(null)
  const show = (m) => {
    setMsg(m)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setMsg(null), 2400)
  }
  return [msg, show]
}

export function useOutsideClose(onClose) {
  const ref = useRef(null)
  useEffect(() => {
    function onDoc(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose()
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [onClose])
  return ref
}

export function Dropdown({ label, options }) {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState(label)
  const ref = useOutsideClose(() => setOpen(false))
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-3 h-9 rounded-lg text-xs font-medium focus-ring"
        style={{ background: C.panel, border: `1px solid ${C.border}`, color: C.text }}
      >
        {selected}
        <ChevronDown size={14} style={{ color: C.textSub }} />
      </button>
      {open && (
        <div
          className="absolute right-0 mt-1 w-40 rounded-lg overflow-hidden z-20"
          style={{ background: C.panelAlt, border: `1px solid ${C.border}` }}
        >
          {options.map((o) => (
            <button
              key={o}
              type="button"
              onClick={() => { setSelected(o); setOpen(false) }}
              className="dropdown-item block w-full text-left px-3 py-2 text-xs"
              style={{ color: o === selected ? C.lime : C.textSub }}
            >
              {o}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function MoreMenu() {
  const [open, setOpen] = useState(false)
  const ref = useOutsideClose(() => setOpen(false))
  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="More options"
        className="icon-btn focus-ring h-6 w-6 flex items-center justify-center rounded-md"
      >
        <MoreHorizontal size={16} style={{ color: C.textMute }} />
      </button>
      {open && (
        <div
          className="absolute right-0 mt-1 w-32 rounded-lg overflow-hidden z-20"
          style={{ background: C.panelAlt, border: `1px solid ${C.border}` }}
        >
          {['Export', 'Edit', 'Delete'].map((o) => (
            <button
              key={o}
              type="button"
              onClick={() => setOpen(false)}
              className="dropdown-item block w-full text-left px-3 py-2 text-xs"
              style={{ color: C.textSub }}
            >
              {o}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function Card({ children, padded = true, className = '', style = {} }) {
  return (
    <div
      className={`dash-card rounded-2xl overflow-hidden ${padded ? 'p-5' : ''} ${className}`}
      style={{ background: C.panel, border: `1px solid ${C.border}`, ...style }}
    >
      {children}
    </div>
  )
}

// A tinted hero panel for one prominent call to action -- the reference uses
// this for its "Productivity Hub" and "AI Assistance" cards. `tone` picks
// which accent the gradient leans on; everything here links somewhere real,
// never a dead button standing in for a feature that does not exist yet.
export function GradientPanel({ eyebrow, title, action, href, tone = 'lime', children }) {
  const from = tone === 'purple' ? C.purple : C.lime
  const fg = tone === 'purple' ? '#FFFFFF' : C.onLime
  return (
    <div
      className="dash-card rounded-2xl p-5 flex flex-col justify-between h-full"
      style={{
        background: `linear-gradient(135deg, ${from}26 0%, ${C.panel} 65%)`,
        border: `1px solid ${C.border}`,
        color: fg === '#FFFFFF' ? C.text : C.text,
      }}
    >
      <div>
        {eyebrow && (
          <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: from }}>
            {eyebrow}
          </div>
        )}
        {title && <div className="text-base font-semibold leading-snug mb-1">{title}</div>}
        {children}
      </div>
      {action && href && (
        <a
          href={href}
          className="focus-ring inline-flex items-center gap-1.5 self-start mt-4 px-3.5 py-2 rounded-full text-xs font-semibold transition-colors"
          style={{ background: from, color: fg }}
        >
          {action}
        </a>
      )}
    </div>
  )
}

// Donut + centered total + a legend that doubles as the color key -- the
// reference's "Team Capacity" / "Monthly Project report" pattern. Takes
// pre-computed [label, value, color][] so callers own their own palette
// choice (usually C.chart) rather than this component guessing one.
export function DonutLegend({ segments, centerLabel, centerValue }) {
  const total = segments.reduce((s, seg) => s + (seg[1] || 0), 0)
  let cumulative = 0
  const R = 42
  const CIRC = 2 * Math.PI * R
  return (
    <div className="flex items-center gap-5">
      <svg width="112" height="112" viewBox="0 0 112 112" className="flex-shrink-0 -rotate-90">
        <circle cx="56" cy="56" r={R} fill="none" stroke={C.panelAlt} strokeWidth="12" />
        {total > 0 && segments.map(([label, value, color], i) => {
          if (!value) return null
          const frac = value / total
          const dash = frac * CIRC
          const gap = CIRC - dash
          const offset = -cumulative * CIRC
          cumulative += frac
          return (
            <circle
              key={label + i}
              cx="56" cy="56" r={R} fill="none"
              stroke={color} strokeWidth="12"
              strokeDasharray={`${dash} ${gap}`}
              strokeDashoffset={offset}
              strokeLinecap="butt"
            />
          )
        })}
      </svg>
      <div className="flex-1 min-w-0">
        {centerValue !== undefined && (
          <div className="mb-2">
            <div className="text-2xl font-bold" style={{ color: C.text }}>{centerValue}</div>
            {centerLabel && <div className="text-[11px]" style={{ color: C.textMute }}>{centerLabel}</div>}
          </div>
        )}
        <div className="flex flex-col gap-1.5">
          {segments.filter(([, v]) => v > 0).map(([label, value, color]) => (
            <div key={label} className="flex items-center gap-2 text-xs">
              <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ background: color }} />
              <span className="truncate" style={{ color: C.textSub }}>{label}</span>
              <span className="ml-auto font-mono tabular-nums" style={{ color: C.text }}>{value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// One row of the reference's "Continue Learning" / "Task Timeline" list --
// a title, a subtitle, and a fit-score-as-progress bar standing in for
// "% complete" since that's the real number this app has for a queued item.
export function ProgressListItem({ href, title, subtitle, pct, badge }) {
  const p = Math.max(0, Math.min(100, pct || 0))
  return (
    <a
      href={href}
      className="link-lime focus-ring flex items-center gap-3 py-2.5 group"
      style={{ borderBottom: `1px solid ${C.border}` }}
    >
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium truncate transition-colors" style={{ color: C.text }}>
          {title}
        </div>
        {subtitle && (
          <div className="text-xs truncate mt-0.5" style={{ color: C.textMute }}>{subtitle}</div>
        )}
        <div className="h-1.5 rounded-full mt-2 overflow-hidden" style={{ background: 'rgba(255,255,255,.08)' }}>
          <div className="h-full rounded-full" style={{ width: `${p}%`, background: C.lime }} />
        </div>
      </div>
      {badge !== undefined && (
        <span className="text-xs font-semibold flex-shrink-0" style={{ color: C.lime }}>{badge}</span>
      )}
    </a>
  )
}

// A colored initial circle -- the leading badge every row in the reference's
// tables carries (its Team page: a photo; here, since there are no uploaded
// photos, an initial on a hashed color reads the same way at a glance).
const AVATAR_COLORS = [C.lime, C.purple, C.teal, C.yellow, C.pink]
function hashColor(seed) {
  let h = 0
  for (let i = 0; i < (seed || '').length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return AVATAR_COLORS[h % AVATAR_COLORS.length]
}

export function Avatar({ name, size = 34 }) {
  const initial = (name || '?').trim().charAt(0).toUpperCase() || '?'
  const bg = hashColor(name || '')
  const dark = bg === C.lime || bg === C.yellow || bg === C.teal
  return (
    <span
      className="rounded-full flex items-center justify-center flex-shrink-0 font-bold"
      style={{
        width: size, height: size, fontSize: size * 0.4,
        background: `${bg}26`, color: bg,
      }}
    >
      {initial}
    </span>
  )
}

// The leading cell of a roster-style row -- avatar, a primary line, and a
// muted secondary line underneath it. Matches the reference's Team table
// (name + role stacked next to a photo) and Task Timeline (name + fraction).
export function RowIdentity({ name, meta, sub }) {
  return (
    <div className="flex items-center gap-3 min-w-0">
      <Avatar name={name} />
      <div className="min-w-0">
        <div className="text-sm font-medium truncate" style={{ color: C.text }}>{name}</div>
        {(meta || sub) && (
          <div className="text-xs truncate mt-0.5" style={{ color: C.textMute }}>
            {meta}{meta && sub ? ' · ' : ''}{sub}
          </div>
        )}
      </div>
    </div>
  )
}

// A small round icon-only action button -- the reference's row-trailing
// action cluster (edit/message/delete as colored circular icon buttons)
// rather than a text link or a bordered rectangular button.
export function RowAction({ href, onClick, icon: Icon, label, tone = 'neutral' }) {
  const style = tone === 'lime'
    ? { background: C.limeDim, color: C.lime }
    : { background: 'rgba(255,255,255,.05)', color: C.textSub }
  const Tag = href ? 'a' : 'button'
  return (
    <Tag
      href={href}
      type={href ? undefined : 'button'}
      onClick={onClick}
      aria-label={label}
      title={label}
      className="icon-btn focus-ring h-8 w-8 rounded-full flex items-center justify-center transition-colors flex-shrink-0"
      style={style}
    >
      <Icon size={14} />
    </Tag>
  )
}
