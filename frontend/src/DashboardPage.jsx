import React from 'react'
import { Briefcase, Award, Sparkles, Search, Clock, Send } from 'lucide-react'
import { C } from './tokens.js'
import { Panel, Empty, GradientPanel, DonutLegend, ProgressListItem } from './components.jsx'
import RankedList from './RankedList.jsx'
import { WorldMap, SourceBars, DiscoveredVsSent, RemoteDonut, FitHeatmap } from './ReachPage.jsx'

// Same tone vocabulary the server-rendered pages use (STATUS_TONE / notice()
// in jobsearch/web/pages.py, html.py). Lime is this palette's one "good"
// color and it is already the primary accent everywhere else, so warn gets
// yellow instead of sharing it -- a caution pill should not look active.
const TONE_COLOR = {
  bad: C.red,
  warn: C.yellow,
  good: C.lime,
  '': C.textSub,
}

// pages.py's dashboard() emits exactly these six labels, in this order.
const STAT_ICON = {
  'positions': Briefcase,
  'accomplishments': Award,
  'skills with evidence': Sparkles,
  'jobs sourced': Search,
  'awaiting review': Clock,
  'sent': Send,
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

// The reference's "Performance Metric" card is one panel holding a 2x2 grid
// of mini-stats, not four separate cards -- this is that inner grid.
function StatTile({ label, value, icon: Icon, tone }) {
  const badge = [
    { bg: C.limeDim, fg: C.lime },
    { bg: C.purpleDim, fg: C.purple },
    { bg: 'rgba(61,224,214,.14)', fg: C.teal },
    { bg: 'rgba(255,210,61,.14)', fg: C.yellow },
  ][tone % 4]
  return (
    <div className="flex flex-col gap-2">
      <span
        className="h-8 w-8 rounded-lg flex items-center justify-center"
        style={{ background: badge.bg, color: badge.fg }}
      >
        <Icon size={15} strokeWidth={2.25} />
      </span>
      <div>
        <div className="text-lg font-bold leading-none" style={{ color: C.text }}>{value}</div>
        <div className="text-[11px] mt-1" style={{ color: C.textMute }}>{label}</div>
      </div>
    </div>
  )
}

// tone-keyed so a status pill reads the same color whether it shows up as a
// pill (StatusPills, elsewhere in the app) or a donut segment (here).
const DONUT_TONE_COLOR = { bad: C.red, warn: C.yellow, good: C.lime, '': C.purple }

export default function DashboardPage({ data }) {
  const {
    notices, stats, jobs_by_status, apps_by_status, model, last_run,
    country_pins, postings_by_country, by_source, by_location,
    sent_vs_discovered, remote, onsite, fit_by_source, recent_queue,
  } = data

  const totalPostings = (postings_by_country || []).reduce((s, [, v]) => s + v, 0)

  const performanceKeys = ['positions', 'accomplishments', 'skills with evidence', 'jobs sourced']
  const performanceStats = performanceKeys
    .map((key) => stats.find((s) => s.label === key))
    .filter(Boolean)

  const appsTotal = (apps_by_status || []).reduce((s, [, n]) => s + n, 0)
  const appDonutSegments = (apps_by_status || []).map(([status, n, tone]) => [
    status, n, DONUT_TONE_COLOR[tone] || C.purple,
  ])
  const awaitingReview = stats.find((s) => s.label === 'awaiting review')?.value ?? 0

  return (
    <>
      <NoticeBanner notices={notices} />

      {/* Hero row 1: grouped profile/pipeline effort, application mix, and
          the one thing most worth doing next -- mirrors the reference's
          Performance Metric | Team Capacity | Productivity Hub layout,
          every number real. */}
      <div className="grid lg:grid-cols-[1.4fr_1fr_1fr] gap-6 mb-6">
        <Panel title="Profile & pipeline" variant="header">
          <div className="grid grid-cols-2 gap-5">
            {performanceStats.map((m, i) => (
              <StatTile key={m.label} label={m.label} value={m.value} icon={STAT_ICON[m.label]} tone={i} />
            ))}
          </div>
        </Panel>

        <Panel title="Applications by status" variant="header">
          {appDonutSegments.length ? (
            <DonutLegend segments={appDonutSegments} centerValue={appsTotal} centerLabel="total" />
          ) : (
            <Empty>No applications yet.</Empty>
          )}
        </Panel>

        <GradientPanel
          eyebrow="Next up"
          title={awaitingReview > 0 ? `${awaitingReview} application${awaitingReview === 1 ? '' : 's'} waiting on you` : 'Queue is clear'}
          action="Review queue"
          href="/queue"
          tone="lime"
        >
          <p className="text-xs mt-1" style={{ color: C.textSub }}>
            Tailored, grounding-checked, and ready for a decision.
          </p>
        </GradientPanel>
      </div>

      {/* Hero row 2: sourcing trend, automation status, and the top of the
          review queue -- Project Revenue | AI Assistance | Continue
          Learning in the reference, mapped to what this app actually has. */}
      <div className="grid lg:grid-cols-[1.2fr_1fr_1.1fr] gap-6 mb-6">
        <Panel title="Discovered vs sent" variant="header">
          <DiscoveredVsSent series={sent_vs_discovered} />
        </Panel>

        <GradientPanel eyebrow="Automation" title={model} tone="purple">
          <dl className="flex flex-col gap-2 mt-3 text-xs">
            <div className="flex items-center justify-between">
              <dt style={{ color: C.textMute }}>Last run</dt>
              <dd className="font-mono" style={{ color: C.text }}>{last_run?.mode || '—'}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt style={{ color: C.textMute }}>Finished</dt>
              <dd className="font-mono" style={{ color: C.text }}>{last_run?.finished_at || 'did not finish'}</dd>
            </div>
          </dl>
        </GradientPanel>

        <Panel title={`Top of the queue (${recent_queue?.length || 0})`} variant="header">
          {recent_queue && recent_queue.length ? (
            <div className="flex flex-col">
              {recent_queue.map((a) => (
                <ProgressListItem
                  key={a.id}
                  href={`/applications/${a.id}`}
                  title={a.role}
                  subtitle={a.company}
                  pct={a.fit_score}
                  badge={a.fit_score != null ? a.fit_score.toFixed(0) : null}
                />
              ))}
            </div>
          ) : (
            <Empty>Nothing drafted yet.</Empty>
          )}
        </Panel>
      </div>

      <div className="grid lg:grid-cols-[1.7fr_1fr] gap-6 mb-6">
        <Panel title="Global reach" variant="header">
          <div className="relative w-full rounded-lg overflow-hidden" style={{ aspectRatio: '2 / 1', maxHeight: 340, background: C.panel }}>
            <WorldMap pins={country_pins} />
          </div>
        </Panel>
        <Panel title="Reach by country" variant="header">
          <div className="mb-4">
            <div className="text-2xl font-bold" style={{ color: C.text }}>
              {Math.round(totalPostings).toLocaleString()}
            </div>
            <div className="text-xs" style={{ color: C.textMute }}>postings, across every named country</div>
          </div>
          <RankedList rows={postings_by_country} maxHeight={340} />
        </Panel>
      </div>

      <div className="grid lg:grid-cols-3 gap-6 mb-6">
        <Panel title="Jobs by status" variant="header">
          <StatusPills rows={jobs_by_status} />
        </Panel>
        <Panel title="Remote vs onsite" variant="header">
          <RemoteDonut remote={remote} onsite={onsite} />
        </Panel>
        <Panel title="Fit score by source" variant="header">
          <FitHeatmap rows={fit_by_source.rows} cols={fit_by_source.cols} grid={fit_by_source.grid} />
        </Panel>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        <Panel title="Source reach" className="md:col-span-2" variant="header">
          <SourceBars rows={by_source} />
        </Panel>
        <Panel title="Top locations" variant="header">
          <RankedList rows={by_location} />
        </Panel>
      </div>
    </>
  )
}
