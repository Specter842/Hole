import React from 'react'
import { C } from './tokens.js'

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
        color: positive ? '#34D399' : C.red,
        background: positive ? 'rgba(52,211,153,.12)' : 'rgba(239,90,90,.12)',
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

export function MetricCard({ label, value, delta }) {
  return (
    <div
      className="rounded-xl p-5"
      style={{ background: C.panel, border: `1px solid ${C.border}` }}
    >
      <div className="flex items-start justify-between">
        <div className="text-2xl font-bold tracking-tight" style={{ color: C.text }}>
          {value}
        </div>
        <MoreDots />
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <span className="text-xs uppercase tracking-wide" style={{ color: C.textMute }}>
          {label}
        </span>
        <DeltaChip delta={delta} />
      </div>
    </div>
  )
}

export function Panel({ title, children, className = '', menu = true }) {
  return (
    <div
      className={`rounded-xl p-6 ${className}`}
      style={{ background: C.panel, border: `1px solid ${C.border}` }}
    >
      {title && (
        <div className="flex items-center justify-between mb-5">
          <div className="text-xs font-semibold uppercase tracking-wide" style={{ color: C.textSub }}>
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
// jobsearch/web/pages.py -- "bad"/"warn" share this palette's one red,
// "good" maps to teal, anything else is a neutral pill.
const TONE_COLOR = {
  bad: C.red,
  warn: C.orange,
  good: C.teal,
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
        <span className="block h-full" style={{ width: `${pct}%`, background: C.teal }} />
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
            <tr key={rowKey ? rowKey(row) : i}>
              {columns.map((col) => (
                <td
                  key={col.key}
                  className="py-3 pr-4 align-top"
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
          style={{ background: C.orange, color: '#1a0d05' }}
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
        style={primary ? { background: C.orange, color: '#1a0d05' } : { color: C.text, border: `1px solid ${C.border}` }}
      >
        {label}
      </button>
    </form>
  )
}
