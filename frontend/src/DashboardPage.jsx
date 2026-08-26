import React from 'react'
import { Briefcase, Award, Sparkles, Search, Clock, Send, ArrowUpRight, MapPin } from 'lucide-react'
import { C } from './tokens.js'
import { Panel, Empty, GradientPanel, DonutLegend, ProgressListItem, Avatar, RowIdentity, RowAction } from './components.jsx'
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

// Reference's "From / To / Date / Search" card -- there is no flight
// itinerary here, so this becomes what this app actually lets you search:
// free text, handed to /jobs?q=... which JobsPage.jsx reads on load and
// uses to prefill its real filter, not a decorative field that goes nowhere.
function QuickSearch() {
  const [q, setQ] = React.useState('')
  return (
    <Panel title="Search" variant="header">
      <form
        onSubmit={(e) => { e.preventDefault(); window.location.href = `/jobs?q=${encodeURIComponent(q)}` }}
        className="flex flex-col gap-3"
      >
        <label className="flex flex-col gap-1 rounded-xl px-3 py-2" style={{ background: C.panelAlt, border: `1px solid ${C.border}` }}>
          <span className="text-[10px] uppercase tracking-wide font-semibold" style={{ color: C.textMute }}>Role, company, or location</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="e.g. platform engineer, remote"
            className="focus-ring bg-transparent outline-none text-sm"
            style={{ color: C.text }}
          />
        </label>
        <button
          type="submit"
          className="btn-primary focus-ring h-10 rounded-xl text-sm font-semibold"
          style={{ background: C.lime, color: C.onLime }}
        >
          Search
        </button>
      </form>
    </Panel>
  )
}

// The reference's flight row (airline, times, price, expand) -- fit score
// stands in for price, since that is the number that actually ranks a
// posting here.
function TopMatchRow({ job }) {
  return (
    <div className="flex items-center gap-3 py-2.5" style={{ borderBottom: `1px solid ${C.border}` }}>
      <Avatar name={job.company} size={32} />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium truncate" style={{ color: C.text }}>{job.title}</div>
        <div className="text-xs truncate mt-0.5" style={{ color: C.textMute }}>{job.company}</div>
      </div>
      <div className="text-sm font-bold flex-shrink-0" style={{ color: C.lime }}>
        {job.fit_score != null ? job.fit_score.toFixed(0) : '—'}
      </div>
      <RowAction href={`/jobs/${job.id}`} icon={ArrowUpRight} label={`Open ${job.title}`} />
    </div>
  )
}

// The reference's floating "ALC -> RUH, $121, 10 seats left, Book now" card
// over the globe -- here, the single best-fit posting.
function TopJobCallout({ job }) {
  if (!job) return null
  return (
    <div
      className="absolute rounded-2xl p-4 w-64 z-10"
      style={{
        top: '38%', left: '50%', transform: 'translate(-50%, -50%)',
        background: C.panel, border: `1px solid ${C.border}`,
        boxShadow: '0 16px 40px -12px rgba(0,0,0,.6)',
      }}
    >
      <div className="flex items-center justify-between text-sm font-bold" style={{ color: C.text }}>
        <span className="truncate">{job.company}</span>
        <span style={{ color: C.lime }}>{job.fit_score != null ? job.fit_score.toFixed(0) : '—'}</span>
      </div>
      <div className="text-xs truncate mt-0.5" style={{ color: C.textSub }}>{job.title}</div>
      <div className="h-px my-3" style={{ background: C.border }} />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] flex items-center gap-1" style={{ color: C.textMute }}>
          <MapPin size={11} /> {job.location || 'Location n/a'}
        </span>
        <a
          href={`/jobs/${job.id}`}
          className="focus-ring text-[11px] font-semibold px-2.5 py-1.5 rounded-lg flex-shrink-0"
          style={{ background: C.bg, color: C.text }}
        >
          View posting
        </a>
      </div>
    </div>
  )
}

// The reference's aircraft spec sheet -- photo, badge, then label/value rows.
// There's no photo for a job posting, so the "photo" slot becomes a large
// company badge instead of leaving an empty frame.
function TopJobSpec({ job }) {
  if (!job) {
    return (
      <Panel variant="header" title="Top match">
        <Empty>No scored jobs yet.</Empty>
      </Panel>
    )
  }
  return (
    <Panel variant="header" menu={false}>
      <div
        className="relative rounded-xl overflow-hidden flex items-center justify-center mb-4"
        style={{ height: 140, background: C.panelAlt }}
      >
        <Avatar name={job.company} size={64} />
        {job.fit_score != null && (
          <span
            className="absolute top-3 right-3 text-[11px] font-bold px-2.5 py-1 rounded-lg"
            style={{ background: C.lime, color: C.onLime }}
          >
            fit {job.fit_score.toFixed(0)}
          </span>
        )}
      </div>
      <div className="text-sm font-bold" style={{ color: C.text }}>{job.company}</div>
      <div className="text-xs mt-0.5 mb-4" style={{ color: C.textSub }}>{job.title}</div>
      <dl className="flex flex-col gap-3 text-sm">
        {[
          ['Location', job.location || '—'],
          ['Remote', job.remote ? 'Yes' : 'No'],
          ['Source', job.source || '—'],
          ['Status', job.status || '—'],
          ['Posted', job.posted_at || '—'],
        ].map(([label, value]) => (
          <div key={label} className="flex items-center justify-between" style={{ borderBottom: `1px solid ${C.border}`, paddingBottom: 10 }}>
            <dt style={{ color: C.textMute }}>{label}</dt>
            <dd className="font-medium text-right" style={{ color: C.text }}>{value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  )
}

export default function DashboardPage({ data }) {
  const {
    notices, stats, jobs_by_status, apps_by_status, model, last_run,
    country_pins, postings_by_country, by_source, by_location,
    sent_vs_discovered, remote, onsite, fit_by_source, recent_queue, top_jobs,
  } = data
  const topJob = (top_jobs && top_jobs[0]) || null

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

      {/* Hero: search + top matches | the globe, with the best match
          floating over it | that match's spec sheet -- the reference's
          From/To/Search + Flights list | globe | aircraft spec panel,
          structurally, not just recolored. */}
      <div className="grid lg:grid-cols-[300px_1fr_300px] gap-6 mb-6">
        <div className="flex flex-col gap-6">
          <QuickSearch />
          <Panel title={`Top matches (${top_jobs?.length || 0})`} variant="header">
            {top_jobs && top_jobs.length ? (
              <div className="flex flex-col">
                {top_jobs.map((j) => <TopMatchRow key={j.id} job={j} />)}
              </div>
            ) : (
              <Empty>No scored jobs yet.</Empty>
            )}
          </Panel>
        </div>

        <Panel title="Global reach" variant="header" className="relative">
          <div className="relative w-full rounded-lg overflow-hidden" style={{ aspectRatio: '1 / 1', minHeight: 420, background: C.panel }}>
            <WorldMap pins={country_pins} />
            <TopJobCallout job={topJob} />
          </div>
        </Panel>

        <TopJobSpec job={topJob} />
      </div>

      {/* Secondary row: profile/pipeline effort, application mix, sourcing
          trend, automation status, and the top of the review queue -- real
          detail beyond the hero, same as the app has always carried. */}
      <div className="grid lg:grid-cols-[1.2fr_1fr_1fr] gap-6 mb-6">
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

      <div className="grid lg:grid-cols-3 gap-6 mb-6">
        <Panel title="Reach by country" variant="header">
          <div className="mb-4">
            <div className="text-2xl font-bold" style={{ color: C.text }}>
              {Math.round(totalPostings).toLocaleString()}
            </div>
            <div className="text-xs" style={{ color: C.textMute }}>postings, across every named country</div>
          </div>
          <RankedList rows={postings_by_country} maxHeight={280} />
        </Panel>
        <Panel title="Jobs by status" variant="header">
          <StatusPills rows={jobs_by_status} />
        </Panel>
        <Panel title="Remote vs onsite" variant="header">
          <RemoteDonut remote={remote} onsite={onsite} />
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

      <div className="grid mt-6">
        <Panel title="Fit score by source" variant="header">
          <FitHeatmap rows={fit_by_source.rows} cols={fit_by_source.cols} grid={fit_by_source.grid} />
        </Panel>
      </div>
    </>
  )
}
