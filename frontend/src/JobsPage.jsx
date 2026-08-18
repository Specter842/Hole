import React from 'react'
import { C } from './tokens.js'
import { Panel, Empty, StatusPill, ScoreBar, DataTable, KV, ActionButton, BackLink } from './components.jsx'

// Ported from jobsearch/web/pages.py's jobs_list()/job_detail() -- same
// query results, restyled into the dark/orange/teal card language. Both
// views share `data.page` to pick between them (main.jsx), and both keep
// the `/jobs` nav item active.

function StatusFilters({ status, statuses }) {
  const all = [null, ...statuses]
  return (
    <div
      className="inline-flex items-center gap-1 p-1 rounded-lg mb-6"
      style={{ background: C.panel, border: `1px solid ${C.border}` }}
    >
      {all.map((s) => {
        const active = (status || null) === s
        return (
          <a
            key={s || 'all'}
            href={s ? `/jobs?status=${s}` : '/jobs'}
            className={`text-xs font-medium uppercase tracking-wide px-3 py-1.5 rounded-md focus-ring transition-colors ${active ? '' : 'filter-pill-inactive'}`}
            style={{
              background: active ? C.panelAlt : 'transparent',
              color: active ? C.text : C.textSub,
            }}
          >
            {s || 'all'}
          </a>
        )
      })}
    </div>
  )
}

const PAGE_SIZE = 50

function Pagination({ page, pageCount, onChange }) {
  if (pageCount <= 1) return null
  return (
    <div className="flex items-center justify-between mt-4 text-xs" style={{ color: C.textSub }}>
      <span>Page {page} of {pageCount}</span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          className="page-btn focus-ring px-3 py-1.5 rounded-md font-medium transition-colors"
          style={{ color: C.textSub }}
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          Previous
        </button>
        <button
          type="button"
          className="page-btn focus-ring px-3 py-1.5 rounded-md font-medium transition-colors"
          style={{ color: C.textSub }}
          disabled={page >= pageCount}
          onClick={() => onChange(page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  )
}

function JobsListPage({ data }) {
  const { jobs, status, statuses } = data
  const [filterText, setFilterText] = React.useState('')
  const [page, setPage] = React.useState(1)
  const filtered = jobs.filter((j) => {
    if (!filterText) return true
    const q = filterText.toLowerCase()
    return [j.title, j.company, j.location].some((v) => (v || '').toLowerCase().includes(q))
  })
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount)
  const pageRows = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  React.useEffect(() => { setPage(1) }, [filterText, status])

  return (
    <>
      <StatusFilters status={status} statuses={statuses} />
      <div className="flex items-center gap-4 mb-4">
        <input
          type="text"
          placeholder="Filter by role, company, location..."
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          className="rounded-lg px-3 py-2 text-sm focus-ring max-w-xs w-full"
          style={{ background: 'rgba(255,255,255,.04)', border: `1px solid ${C.border}`, color: C.text }}
        />
        <span className="text-xs font-mono uppercase tracking-wide" style={{ color: C.textMute }}>
          {filtered.length} of {jobs.length}
        </span>
      </div>
      <Panel menu={false}>
        <DataTable
          empty="No jobs sourced yet. Run the pipeline, or add sources to config.toml."
          rowKey={(j) => j.id}
          columns={[
            { key: 'fit', label: 'Fit', render: (j) => <ScoreBar score={j.fit_score} /> },
            {
              key: 'role',
              label: 'Role',
              render: (j) => (
                <>
                  <a href={`/jobs/${j.id}`} style={{ color: C.text, borderBottom: `1px solid ${C.border}` }}>
                    {j.title}
                  </a>
                  {j.skip_reason && (
                    <div className="text-xs mt-1" style={{ color: C.textMute }}>{j.skip_reason}</div>
                  )}
                </>
              ),
            },
            { key: 'company', label: 'Company' },
            {
              key: 'location',
              label: 'Location',
              render: (j) => (
                <>
                  {j.location} {j.remote && <StatusPill label="remote" tone="good" />}
                </>
              ),
            },
            { key: 'status', label: 'Status', render: (j) => <StatusPill label={j.status} tone={j.tone} /> },
            { key: 'source', label: 'Source' },
          ]}
          rows={pageRows}
        />
        <Pagination page={safePage} pageCount={pageCount} onChange={setPage} />
      </Panel>
    </>
  )
}

function ApplicationsMini({ applications }) {
  if (!applications.length) return null
  return (
    <Panel title="Applications" className="mt-6">
      <DataTable
        rowKey={(a) => a.id}
        columns={[
          { key: 'id', label: 'ID', render: (a) => <a href={`/applications/${a.id}`} style={{ color: C.teal }}>#{a.id}</a> },
          { key: 'status', label: 'Status', render: (a) => <StatusPill label={a.status} tone={a.tone} /> },
          {
            key: 'grounding',
            label: 'Grounding',
            render: (a) => <StatusPill label={a.grounding_status} tone={a.grounding_clean ? 'good' : 'warn'} />,
          },
          { key: 'date', label: 'Created' },
        ]}
        rows={applications}
      />
    </Panel>
  )
}

function JobDetailPage({ data }) {
  const { job, applications, token } = data
  return (
    <>
      <BackLink href="/jobs" label="Back to Jobs" />
      <div className="flex gap-3 mb-6 text-sm">
        {job.url && (
          <a href={job.url} target="_blank" rel="noreferrer noopener" style={{ color: C.teal }}>
            posting
          </a>
        )}
        {job.apply_url && (
          <a href={job.apply_url} target="_blank" rel="noreferrer noopener" style={{ color: C.teal }}>
            apply form
          </a>
        )}
      </div>

      <Panel menu={false}>
        <KV
          items={[
            { label: 'Fit score', value: <ScoreBar score={job.fit_score} /> },
            { label: 'Status', value: <StatusPill label={job.status} tone={job.tone} /> },
            { label: 'Source', value: job.source },
            { label: 'Location', value: job.location },
            { label: 'Compensation', value: job.compensation },
            { label: 'Posted', value: job.posted_at },
            { label: 'Discovered', value: job.discovered_at },
            { label: 'Skipped because', value: job.skip_reason },
          ]}
        />
      </Panel>

      {applications.length > 0 ? (
        <ApplicationsMini applications={applications} />
      ) : (
        <div className="mt-6">
          <ActionButton
            action={`/jobs/${job.id}/tailor`}
            token={token}
            label="Tailor for this posting"
            primary
            confirm="Tailoring makes one model API call. Continue?"
          />
        </div>
      )}

      <Panel title="Posting" className="mt-8">
        {job.description ? (
          <pre
            className="whitespace-pre-wrap text-sm leading-relaxed font-mono"
            style={{ color: C.textSub }}
          >
            {job.description}
          </pre>
        ) : (
          <Empty />
        )}
      </Panel>
    </>
  )
}

export default function JobsPage({ data }) {
  if (data.page === 'job_detail') return <JobDetailPage data={data} />
  return <JobsListPage data={data} />
}
