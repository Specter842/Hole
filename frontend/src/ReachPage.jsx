import React, { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts'
import { C } from './tokens.js'
import { Card, Dropdown, MoreMenu, useToast, Empty } from './components.jsx'
import { WORLD_LAND_PATH, WORLD_BORDERS_PATH } from './worldLandPath.js'

const tooltipStyle = {
  background: C.panelAlt,
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  color: C.text,
  fontSize: 12,
}

export function WorldMap({ pins }) {
  return (
    <>
      <svg viewBox="0 0 1000 500" preserveAspectRatio="none" className="absolute inset-0 w-full h-full block">
        <path d={WORLD_LAND_PATH} fill={C.mapLand} stroke="none" />
        <path d={WORLD_BORDERS_PATH} fill="none" stroke={C.mapBorder} strokeWidth="0.6" />
      </svg>
      {pins && pins.map((p, i) => (
        <div
          key={i}
          className="absolute flex items-center gap-1 px-2 py-1 rounded-full font-semibold shadow z-10"
          style={{
            top: `${p.top}%`,
            left: `${p.left}%`,
            transform: 'translate(-50%, -100%)',
            background: '#F5F5F5',
            color: '#111',
            fontSize: '11px',
          }}
        >
          <span>{p.flag}</span>{Math.round(p.value).toLocaleString()}
        </div>
      ))}
    </>
  )
}

function heatColor(t) {
  t = Math.min(1, Math.max(0, t))
  const from = { r: 22, g: 27, b: 29 }
  const to = { r: 138, g: 211, b: 216 }
  const r = Math.round(from.r + (to.r - from.r) * t)
  const g = Math.round(from.g + (to.g - from.g) * t)
  const b = Math.round(from.b + (to.b - from.b) * t)
  return `rgb(${r}, ${g}, ${b})`
}

const RADIAN = Math.PI / 180
function renderPieLabel({ cx, cy, midAngle, outerRadius, percent }) {
  const cos = Math.cos(-RADIAN * midAngle)
  const sin = Math.sin(-RADIAN * midAngle)
  const sx = cx + outerRadius * cos
  const sy = cy + outerRadius * sin
  const mx = cx + (outerRadius + 16) * cos
  const my = cy + (outerRadius + 16) * sin
  const ex = mx + (cos >= 0 ? 1 : -1) * 12
  return (
    <g>
      <path d={`M${sx},${sy}L${mx},${my}L${ex},${my}`} stroke="#555" fill="none" />
      <text
        x={ex + (cos >= 0 ? 1 : -1) * 4}
        y={my}
        textAnchor={cos >= 0 ? 'start' : 'end'}
        dominantBaseline="central"
        fill={C.text}
        fontSize={12}
      >
        {`${Math.round(percent * 100)}%`}
      </text>
    </g>
  )
}

export function DiscoveredVsSent({ series }) {
  if (!series || !series.days) return <Empty />
  const barData = []
  for (let i = 0; i < series.days.length; i++) {
    barData.push({
      day: series.days[i],
      discovered: series.discovered[i],
      sent: series.sent[i]
    })
  }

  return (
    <>
      <div className="flex items-center gap-3 mb-2 text-xs" style={{ color: C.textSub }}>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: C.teal }} />Discovered</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full" style={{ background: C.barDark, border: `1px solid ${C.border}` }} />Sent</span>
      </div>
      <div style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={barData} barGap={-18} barCategoryGap="24%">
            <XAxis dataKey="day" tick={{ fill: C.textSub, fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis
              tick={{ fill: C.textSub, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: 'rgba(255,255,255,0.04)' }}
              contentStyle={tooltipStyle}
              labelStyle={{ color: C.textSub }}
            />
            <Bar dataKey="sent" fill={C.barDark} radius={[3, 3, 0, 0]} barSize={18} />
            <Bar dataKey="discovered" fill={C.teal} radius={[3, 3, 0, 0]} barSize={10} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  )
}

export function RemoteDonut({ remote, onsite }) {
  const pieData = [
    { name: 'Remote', value: remote || 0, color: C.teal },
    { name: 'Onsite', value: onsite || 0, color: C.orange }
  ]

  return (
    <>
      <div style={{ height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              innerRadius="62%"
              outerRadius="88%"
              startAngle={90}
              endAngle={-270}
              stroke="none"
              label={renderPieLabel}
              labelLine={false}
            >
              {pieData.map((p, i) => (
                <Cell key={i} fill={p.color} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="flex items-center justify-center gap-4 text-xs mt-1" style={{ color: C.textSub }}>
        {pieData.map((p) => (
          <span key={p.name} className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
            {p.name}
          </span>
        ))}
      </div>
    </>
  )
}

export function FitHeatmap({ rows, cols, grid }) {
  let heatMax = 0
  if (grid) {
    grid.forEach(row => row.forEach(v => { if (v > heatMax) heatMax = v }))
  }
  const heatRows = rows || []
  const heatCols = cols || []

  return (
    <div className="flex gap-1 overflow-x-auto">
      <div className="flex flex-col justify-between pr-1" style={{ color: C.textMute }}>
        {heatRows.map((h) => (
          <div key={h} className="flex items-center" style={{ height: '16px', fontSize: '10px' }}>{h}</div>
        ))}
      </div>
      <div className="flex-1">
        <div className="space-y-1 flex" style={{gap: '4px'}}>
          {heatCols.map((c, ci) => (
            <div key={ci} className="flex flex-col gap-1">
              {heatRows.map((_, ri) => {
                const v = grid?.[ri]?.[ci] || 0
                const t = heatMax ? v / heatMax : 0
                return (
                  <div
                    key={ri}
                    className="rounded-sm"
                    style={{ width: '16px', height: '16px', background: heatColor(t) }}
                    title={`${heatRows[ri]} · ${c}: ${v}`}
                  />
                )
              })}
              <div className="text-center mt-1" style={{ color: C.textMute, fontSize: '10px', writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}>
                {c}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function SourceBars({ rows }) {
  if (!rows || !rows.length) return <Empty />
  const data = rows.map(([name, n]) => ({ name, n }))
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" horizontal={false} />
        <XAxis type="number" tick={{ fill: C.textMute, fontSize: 11 }} axisLine={false} tickLine={false} />
        <YAxis
          type="category"
          dataKey="name"
          width={110}
          tick={{ fill: C.textSub, fontSize: 12 }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,.04)' }} />
        <Bar dataKey="n" fill={C.orange} radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export default function ReachPage({ data }) {
  const [toast, showToast] = useToast()
  
  const {
    stats = [], postings_by_country = [], country_pins = [],
    sent_vs_discovered, remote, onsite, fit_by_source
  } = data

  const totalPostings = postings_by_country.reduce((s, [, v]) => s + v, 0)
  
  const topRegions = postings_by_country.slice(0, 5).map(([name, value]) => {
    const pct = totalPostings > 0 ? Math.round((value / totalPostings) * 100) : 0
    const pin = country_pins.find((p) => p.name === name)
    return { name, value, pct, flag: pin ? pin.flag : '🌐' }
  })

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-4">
        {stats.map((m) => {
          const positive = (m.delta || 0) >= 0
          const changeStr = m.delta ? `${positive ? '+' : ''}${m.delta.toFixed(2)}%` : '0%'
          return (
            <Card key={m.label}>
              <div className="flex items-start justify-between mb-3">
                <div className="font-medium uppercase tracking-wide truncate" style={{ color: C.textSub, fontSize: '11px' }}>
                  {m.label}
                </div>
                <MoreMenu />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold">{m.value}</span>
                <span className="font-medium" style={{ fontSize: '13px', color: positive ? C.teal : C.red }}>
                  {changeStr}
                </span>
              </div>
              <div className="text-xs mt-1" style={{ color: C.textMute }}>vs last month</div>
            </Card>
          )
        })}
      </div>

      <Card padded={false}>
        <div className="p-5 pb-4 flex items-center justify-between">
          <div className="text-sm font-semibold">Global Reach by Region</div>
          <button type="button" onClick={() => showToast('Opening details…')} className="link-teal focus-ring text-xs flex items-center gap-1" style={{ color: C.teal }}>
            View Details <ArrowRight size={12} />
          </button>
        </div>
        <div className="flex gap-5 px-5 pb-5">
          <div className="flex-1 relative rounded-lg overflow-hidden" style={{ aspectRatio: '2 / 1', maxHeight: 340, background: C.panel }}>
            <WorldMap pins={country_pins} />
          </div>
          <div className="w-72 flex-shrink-0 rounded-lg p-4" style={{ background: C.panelAlt }}>
            <div className="text-3xl font-bold">{Math.round(totalPostings).toLocaleString()}</div>
            <div className="text-xs mb-4" style={{ color: C.textSub }}>
              Active postings <span style={{ color: C.teal }}>+0.00%</span>
            </div>
            <div className="h-px mb-4" style={{ background: C.border }} />
            <div className="space-y-3">
              {topRegions.map((r) => (
                <div key={r.name}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="flex items-center gap-2">
                      <span className="rounded-full flex items-center justify-center overflow-hidden" style={{ fontSize: '10px', height: '16px', width: '16px' }}>
                        {r.flag}
                      </span>
                      {r.name}
                    </span>
                    <span style={{ color: C.textSub }}>{r.pct}%</span>
                  </div>
                  <div className="h-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.08)' }}>
                    <div className="h-1.5 rounded-full" style={{ width: `${r.pct}%`, background: C.teal }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-3 gap-5">
        <Card>
          <div className="flex items-start justify-between mb-4">
            <div className="text-sm font-semibold leading-tight">Discovered vs Sent —<br />Annual View</div>
            <div className="flex items-center gap-2">
              <Dropdown label="Month" options={['Week', 'Month', 'Quarter', 'Year']} />
              <MoreMenu />
            </div>
          </div>
          <DiscoveredVsSent series={sent_vs_discovered} />
        </Card>

        <Card>
          <div className="flex items-start justify-between mb-4">
            <div className="text-sm font-semibold">Remote vs Onsite</div>
            <div className="flex items-center gap-2">
              <Dropdown label="Month" options={['Week', 'Month', 'Quarter', 'Year']} />
              <MoreMenu />
            </div>
          </div>
          <RemoteDonut remote={remote} onsite={onsite} />
        </Card>

        <Card>
          <div className="flex items-start justify-between mb-4">
            <div className="text-sm font-semibold">Fit Score by Source</div>
            <div className="flex items-center gap-2">
              <Dropdown label="Month" options={['Week', 'Month', 'Quarter', 'Year']} />
              <MoreMenu />
            </div>
          </div>
          <FitHeatmap rows={fit_by_source?.rows} cols={fit_by_source?.cols} grid={fit_by_source?.grid} />
        </Card>
      </div>
    </div>
  )
}
