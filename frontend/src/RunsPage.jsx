import React from 'react'
import { History } from 'lucide-react'
import { C } from './tokens.js'
import { Panel, StatusPill, DataTable } from './components.jsx'

// Ported from jobsearch/web/pages.py's runs() -- one row per pipeline run.

const MODE_TONE = { autonomous: C.lime, 'review-only': C.purple, 'dry-run': C.textMute }

function RunIdentity({ run }) {
  const tone = MODE_TONE[run.mode] || C.textMute
  return (
    <div className="flex items-center gap-3">
      <span
        className="h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ background: `${tone}26`, color: tone }}
      >
        <History size={14} />
      </span>
      <div className="min-w-0">
        <div className="text-sm font-medium" style={{ color: C.text }}>#{run.id} &middot; {run.mode}</div>
        <div className="text-xs mt-0.5 font-mono truncate" style={{ color: C.textMute }}>{run.started_at}</div>
      </div>
    </div>
  )
}

export default function RunsPage({ data }) {
  const { runs } = data
  return (
    <>
      <p className="text-sm mb-6" style={{ color: C.textSub }}>
        For auditing an unattended night.
      </p>
      <Panel menu={false}>
        <DataTable
          empty="No runs recorded yet."
          rowKey={(r) => r.id}
          columns={[
            { key: 'run', label: 'Run', render: (r) => <RunIdentity run={r} /> },
            {
              key: 'finished',
              label: 'Finished',
              render: (r) => r.finished_at || <span style={{ color: C.textMute }}>did not finish</span>,
            },
            { key: 'notes', label: 'Notes', render: (r) => r.summary },
          ]}
          rows={runs}
        />
      </Panel>
    </>
  )
}
