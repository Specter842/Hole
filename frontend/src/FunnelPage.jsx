import React from 'react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell } from 'recharts'
import { C } from './tokens.js'
import { MetricCard, Panel, Empty } from './components.jsx'

const tooltipStyle = {
  background: C.panelAlt,
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  color: C.text,
  fontSize: 12,
}

function ColumnChart({ rows, color = C.teal }) {
  if (!rows || !rows.length) return <Empty />
  const data = rows.map(([label, n]) => ({ label, n }))
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ left: -12, right: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" vertical={false} />
        <XAxis dataKey="label" tick={{ fill: C.textMute, fontSize: 10 }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fill: C.textMute, fontSize: 10 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,.04)' }} />
        <Bar dataKey="n" fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

function FunnelBars({ rows }) {
  if (!rows || !rows.length) return <Empty />
  const data = rows.map(([label, n]) => ({ label, n }))
  const colors = [C.teal, C.teal, C.orange, C.orange, C.orange]
  return (
    <ResponsiveContainer width="100%" height={rows.length * 46 + 20}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" horizontal={false} />
        <XAxis type="number" tick={{ fill: C.textMute, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="label" width={90} tick={{ fill: C.textSub, fontSize: 12 }} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,.04)' }} />
        <Bar dataKey="n" radius={[0, 4, 4, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={colors[i % colors.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

function SplitBar({ evidenced, unevidenced }) {
  const total = evidenced + unevidenced
  const pct = total ? (evidenced / total) * 100 : 0
  return (
    <div>
      <div className="h-6 rounded-md overflow-hidden flex" style={{ background: 'rgba(255,255,255,.06)' }}>
        {evidenced > 0 && <div style={{ width: `${pct}%`, background: C.teal }} />}
        {unevidenced > 0 && <div style={{ width: `${100 - pct}%`, background: C.red }} />}
      </div>
      <div className="flex gap-6 mt-3 text-xs" style={{ color: C.textSub }}>
        <span className="flex items-center gap-1.5">
          <i className="inline-block w-2 h-2 rounded-sm" style={{ background: C.teal }} />
          evidenced <b style={{ color: C.text }}>{evidenced}</b>
        </span>
        <span className="flex items-center gap-1.5">
          <i className="inline-block w-2 h-2 rounded-sm" style={{ background: C.red }} />
          unevidenced <b style={{ color: C.text }}>{unevidenced}</b>
        </span>
      </div>
    </div>
  )
}

export default function FunnelPage({ data }) {
  const { stages, fit_histogram, evidenced, unevidenced, top_skills } = data

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        {stages.map(([label, value]) => (
          <MetricCard key={label} label={label} value={Math.round(value).toLocaleString()} />
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <Panel title="Fit score distribution">
          <ColumnChart rows={fit_histogram} color={C.orange} />
        </Panel>
        <Panel title="Postings reaching each stage">
          <FunnelBars rows={stages} />
        </Panel>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Panel title="Claimable vs unusable">
          <SplitBar evidenced={evidenced} unevidenced={unevidenced} />
        </Panel>
        <Panel title="Most-evidenced skills">
          <ColumnChart rows={top_skills} color={C.teal} />
        </Panel>
      </div>
    </>
  )
}
