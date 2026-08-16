import React from 'react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell,
} from 'recharts'
import { C } from './tokens.js'
import { MetricCard, Panel, Empty } from './components.jsx'
import RankedList from './RankedList.jsx'

const tooltipStyle = {
  background: C.panelAlt,
  border: `1px solid ${C.border}`,
  borderRadius: 8,
  color: C.text,
  fontSize: 12,
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

// Two genuinely distinct real series (postings discovered vs applications
// sent, per day) -- replaces the reference's "Direct vs Organic" mock chart,
// which had no honest equivalent in this app's data.
function DiscoveredVsSent({ series }) {
  const { days, discovered, sent } = series || {}
  if (!days || !days.length) return <Empty />
  const data = days.map((day, i) => ({ day, discovered: discovered[i], sent: sent[i] }))
  return (
    <>
      <div className="flex items-center gap-4 mb-3 text-xs" style={{ color: C.textSub }}>
        <span className="flex items-center gap-1.5">
          <i className="inline-block w-2 h-2 rounded-full" style={{ background: C.teal }} />
          Discovered
        </span>
        <span className="flex items-center gap-1.5">
          <i className="inline-block w-2 h-2 rounded-full" style={{ background: C.tealDark }} />
          Sent
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ left: -12, right: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.06)" vertical={false} />
          <XAxis dataKey="day" tick={{ fill: C.textMute, fontSize: 10 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: C.textMute, fontSize: 10 }} axisLine={false} tickLine={false} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(255,255,255,.04)' }} />
          <Bar dataKey="discovered" fill={C.teal} radius={[3, 3, 0, 0]} />
          <Bar dataKey="sent" fill={C.tealDark} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </>
  )
}

function RemoteDonut({ remote, onsite }) {
  const total = remote + onsite
  const data = [
    { name: 'Remote', value: remote, color: C.teal },
    { name: 'Onsite', value: onsite, color: C.orange },
  ]
  const pct = total ? Math.round((remote / total) * 100) : 0
  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: 200, height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              innerRadius={62}
              outerRadius={90}
              paddingAngle={total ? 2 : 0}
              stroke="none"
            >
              {data.map((d) => (
                <Cell key={d.name} fill={d.color} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <div className="text-2xl font-bold" style={{ color: C.text }}>{pct}%</div>
          <div className="text-[10px] uppercase tracking-wide" style={{ color: C.textMute }}>remote</div>
        </div>
      </div>
      <div className="flex gap-5 mt-3">
        {data.map((d) => (
          <span key={d.name} className="flex items-center gap-1.5 text-xs" style={{ color: C.textSub }}>
            <i className="inline-block w-2 h-2 rounded-full" style={{ background: d.color }} />
            {d.name} <b style={{ color: C.text }}>{Math.round(d.value).toLocaleString()}</b>
          </span>
        ))}
      </div>
    </div>
  )
}

function FitHeatmap({ rows, cols, grid }) {
  if (!rows || !rows.length || !cols || !cols.length) return <Empty />
  let max = 0
  grid.forEach((row) => row.forEach((v) => { if (v > max) max = v }))
  const legendSteps = [0.15, 0.4, 0.65, 0.9]
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="border-separate" style={{ borderSpacing: 3 }}>
          <tbody>
            {rows.map((rowLabel, ri) => (
              <tr key={rowLabel}>
                <td className="text-xs pr-3 text-right whitespace-nowrap" style={{ color: C.textSub }}>
                  {rowLabel}
                </td>
                {cols.map((colLabel, ci) => {
                  const v = grid[ri][ci] || 0
                  const t = max ? v / max : 0
                  return (
                    <td key={colLabel}>
                      <div
                        title={`${rowLabel} · ${colLabel}: ${v}`}
                        className="w-7 h-7 rounded"
                        style={{ background: t === 0 ? 'rgba(255,255,255,.04)' : `rgba(138,211,216,${0.12 + t * 0.78})` }}
                      />
                    </td>
                  )
                })}
              </tr>
            ))}
            <tr>
              <td />
              {cols.map((c) => (
                <td key={c} className="text-[10px] text-center pt-1" style={{ color: C.textMute }}>
                  {c}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-3 mt-4 text-[10px]" style={{ color: C.textMute }}>
        <span>fit-score intensity</span>
        {legendSteps.map((t) => (
          <span key={t} className="flex items-center gap-1">
            <i className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: `rgba(138,211,216,${0.12 + t * 0.78})` }} />
            {Math.round(max * t).toLocaleString()}+
          </span>
        ))}
      </div>
    </div>
  )
}

// Very low-detail continent silhouettes, expressed as [lon, lat] vertices and
// projected with the exact same plain equirectangular formula as the backend's
// geo.project_equirect (see jobsearch/web/geo.py) -- x = (lon+180)/360*100,
// y = (90-lat)/180*50 -- so a pin's top/left % always lands on its own
// landmass in this backdrop, not just near it.
const CONTINENTS = [
  // North America
  [[-165, 68], [-140, 70], [-95, 75], [-80, 73], [-70, 60], [-55, 52], [-60, 45],
    [-65, 40], [-75, 35], [-80, 25], [-90, 15], [-85, 10], [-92, 14], [-105, 20],
    [-115, 28], [-124, 40], [-124, 48], [-130, 55], [-140, 60], [-165, 68]],
  // South America
  [[-80, 10], [-77, 5], [-70, -5], [-70, -18], [-72, -30], [-70, -40], [-68, -52],
    [-65, -55], [-58, -52], [-55, -35], [-48, -25], [-40, -10], [-50, 0],
    [-60, 5], [-70, 8], [-80, 10]],
  // Europe
  [[-10, 36], [-9, 43], [0, 49], [5, 51], [10, 54], [20, 55], [25, 60], [30, 65],
    [20, 70], [10, 71], [-5, 63], [-10, 55], [-10, 45], [-10, 36]],
  // Africa
  [[-17, 15], [-10, 5], [10, 4], [9, -5], [12, -18], [18, -35], [30, -30],
    [35, -20], [40, -5], [42, 5], [48, 10], [45, 15], [38, 20], [33, 31],
    [25, 32], [10, 33], [-5, 35], [-10, 30], [-17, 15]],
  // Asia
  [[30, 68], [45, 70], [60, 72], [75, 73], [90, 75], [110, 73], [130, 70],
    [145, 62], [140, 50], [130, 45], [125, 38], [122, 30], [115, 22], [105, 10],
    [100, 5], [95, 15], [90, 22], [85, 25], [75, 20], [70, 25], [68, 35],
    [60, 38], [50, 40], [45, 38], [40, 42], [35, 42], [28, 42], [28, 55], [30, 68]],
  // Australia
  [[113, -22], [120, -20], [130, -12], [137, -12], [142, -11], [145, -17],
    [150, -22], [153, -28], [150, -35], [145, -38], [140, -38], [135, -35],
    [129, -32], [122, -34], [115, -33], [113, -22]],
]

function projectXY(lon, lat) {
  const x = ((lon + 180) / 360) * 100
  const y = ((90 - lat) / 180) * 50
  return [x, y]
}

function continentPath(vertices) {
  return vertices
    .map(([lon, lat], i) => {
      const [x, y] = projectXY(lon, lat)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ') + ' Z'
}

export function WorldMap({ pins }) {
  if (!pins || !pins.length) return <Empty />
  return (
    <div
      className="relative w-full rounded-lg overflow-hidden"
      style={{ aspectRatio: '2 / 1', background: C.panelAlt }}
    >
      {/* Flat gray continent silhouettes -- no borders, no labels -- with
          pins positioned by real equirectangular-projected lat/lon (see
          geo.project_equirect) on top. */}
      <svg viewBox="0 0 100 50" className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
        <rect x="0" y="0" width="100" height="50" fill={C.panelAlt} />
        {CONTINENTS.map((vertices, i) => (
          <path key={i} d={continentPath(vertices)} fill={C.mapLand} stroke="none" />
        ))}
      </svg>
      {pins.map((pin) => (
        <div
          key={pin.name}
          className="absolute -translate-x-1/2 -translate-y-1/2 flex flex-col items-center"
          style={{ top: `${pin.top}%`, left: `${pin.left}%` }}
          title={pin.name}
        >
          <span
            className="flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap"
            style={{ background: C.panel, border: `1px solid ${C.border}`, color: C.text }}
          >
            <span>{pin.flag}</span>
            {Math.round(pin.value).toLocaleString()}
          </span>
          <span className="mt-0.5 h-2 w-2 rounded-full" style={{ background: C.orange }} />
        </div>
      ))}
    </div>
  )
}

export default function ReachPage({ data }) {
  const {
    stats, by_source, by_location, postings_by_country, applications_by_country,
    country_pins, sent_vs_discovered, remote, onsite, fit_by_source,
  } = data

  const totalPostings = (postings_by_country || []).reduce((s, [, v]) => s + v, 0)

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {stats.map((m) => (
          <MetricCard key={m.label} label={m.label} value={m.value} delta={m.delta} />
        ))}
      </div>

      <div className="grid lg:grid-cols-[1.7fr_1fr] gap-6 mb-6">
        <Panel title="Global reach by region">
          <WorldMap pins={country_pins} />
        </Panel>
        <Panel title="Reach by country">
          <div className="mb-4">
            <div className="text-2xl font-bold" style={{ color: C.text }}>
              {Math.round(totalPostings).toLocaleString()}
            </div>
            <div className="text-xs" style={{ color: C.textMute }}>postings, across every named country</div>
          </div>
          <RankedList rows={postings_by_country} />
        </Panel>
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mb-6">
        <Panel title="Discovered vs sent">
          <DiscoveredVsSent series={sent_vs_discovered} />
        </Panel>
        <Panel title="Remote vs onsite">
          <RemoteDonut remote={remote} onsite={onsite} />
        </Panel>
        <Panel title="Fit score by source">
          <FitHeatmap rows={fit_by_source.rows} cols={fit_by_source.cols} grid={fit_by_source.grid} />
        </Panel>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <Panel title="Source reach" className="md:col-span-2">
          <SourceBars rows={by_source} />
        </Panel>
        <Panel title="Top locations">
          <RankedList rows={by_location} />
        </Panel>
      </div>

      {applications_by_country && applications_by_country.length > 0 && (
        <div className="grid gap-6 mt-6">
          <Panel title="Applications sent, by country">
            <RankedList rows={applications_by_country} />
          </Panel>
        </div>
      )}
    </>
  )
}
