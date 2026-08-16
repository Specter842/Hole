import React from 'react'
import { C } from './tokens.js'
import { MetricCard, Panel, Empty } from './components.jsx'
import RankedList from './RankedList.jsx'
import { WorldMap, SourceBars, DiscoveredVsSent, RemoteDonut, FitHeatmap } from './ReachPage.jsx'

// Same tone vocabulary the server-rendered pages use (STATUS_TONE / notice()
// in jobsearch/web/pages.py, html.py) -- "bad"/"warn" map to the one red this
// palette has, "good" to teal, anything else to a neutral grey pill.
const TONE_COLOR = {
  bad: C.red,
  warn: C.orange,
  good: C.teal,
  '': C.textSub,
}

// The config-problem/autonomous-mode notices the old server-rendered
// dashboard led with (jobsearch/web/pages.py's old `dashboard()`). Dropping
// these silently would be a regression -- that function's own comments call
// this "honesty first": telling the user when the pipeline can't, or will
// autonomously, send.
function NoticeBanner({ notices }) {
  if (!notices || !notices.length) return null
  return (
    <div className="flex flex-col gap-3 mb-6">
      {notices.map((n, i) => (
        <div
          key={i}
          className="rounded-xl p-4 text-sm"
          style={{
            background: 'rgba(255,255,255,.03)',
            border: `1px solid ${TONE_COLOR[n.tone] || C.border}`,
            color: C.textSub,
          }}
        >
          <div className="font-semibold mb-1" style={{ color: TONE_COLOR[n.tone] || C.text }}>
            {n.text}
          </div>
          {n.items && n.items.length > 0 && (
            <ul className="list-disc pl-5 mt-1 space-y-0.5">
              {n.items.map((item, j) => (
                <li key={j}>{item}</li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  )
}

// Rows arrive as [status, count, tone] -- tone computed server-side by the
// same STATUS_TONE table pages.py already uses for the server-rendered pill()
// helper, so a status reads the same colour everywhere in the app.
function StatusPills({ rows }) {
  if (!rows || !rows.length) return <Empty />
  return (
    <div className="flex flex-wrap gap-2">
      {rows.map(([status, n, tone]) => (
        <span
          key={status}
          className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full"
          style={{ background: C.panelAlt, border: `1px solid ${C.border}`, color: C.textSub }}
        >
          <i
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ background: TONE_COLOR[tone] || C.textMute }}
          />
          {status}
          <b style={{ color: C.text }}>{Math.round(n).toLocaleString()}</b>
        </span>
      ))}
    </div>
  )
}

function LastRun({ run }) {
  if (!run) return <Empty>No runs recorded yet.</Empty>
  return (
    <dl className="grid gap-2.5 text-sm">
      {[
        ['Started', run.started_at],
        ['Mode', run.mode],
        ['Finished', run.finished_at || 'did not finish'],
      ].map(([label, value]) => (
        <div key={label} className="flex items-center justify-between gap-4">
          <dt style={{ color: C.textMute }}>{label}</dt>
          <dd className="font-mono text-xs text-right" style={{ color: C.text }}>{value || '—'}</dd>
        </div>
      ))}
    </dl>
  )
}

export default function DashboardPage({ data }) {
  const {
    notices, stats, jobs_by_status, apps_by_status, model, last_run,
    country_pins, postings_by_country, by_source, by_location,
    sent_vs_discovered, remote, onsite, fit_by_source,
  } = data

  const totalPostings = (postings_by_country || []).reduce((s, [, v]) => s + v, 0)

  return (
    <>
      <NoticeBanner notices={notices} />

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        {stats.map((m) => (
          <MetricCard key={m.label} label={m.label} value={m.value} />
        ))}
      </div>

      <div className="grid lg:grid-cols-[1.7fr_1fr] gap-6 mb-6">
        <Panel title="Global reach">
          <WorldMap pins={country_pins} />
        </Panel>
        <Panel title="Reach by country">
          <div className="mb-4">
            <div className="text-2xl font-bold" style={{ color: C.text }}>
              {Math.round(totalPostings).toLocaleString()}
            </div>
            <div className="text-xs" style={{ color: C.textMute }}>postings, across every named country</div>
          </div>
          <RankedList rows={postings_by_country} maxHeight={340} />
        </Panel>
      </div>

      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        <Panel title="Jobs by status">
          <StatusPills rows={jobs_by_status} />
        </Panel>
        <Panel title="Applications by status">
          <StatusPills rows={apps_by_status} />
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

      <div className="grid md:grid-cols-3 gap-6 mb-6">
        <Panel title="Source reach" className="md:col-span-2">
          <SourceBars rows={by_source} />
        </Panel>
        <Panel title="Top locations">
          <RankedList rows={by_location} />
        </Panel>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Panel title="Last pipeline run">
          <LastRun run={last_run} />
        </Panel>
        <Panel title="Model">
          <div className="font-mono text-xs" style={{ color: C.textSub }}>{model}</div>
        </Panel>
      </div>
    </>
  )
}
