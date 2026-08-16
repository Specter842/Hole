import React from 'react'
import { C } from './tokens.js'
import { Panel, StatusPill, DataTable } from './components.jsx'

// Ported from jobsearch/web/pages.py's runs() -- one row per pipeline run.

export default function RunsPage({ data }) {
  const { runs } = data
  return (
    <>
      <p className="text-sm mb-6" style={{ color: C.textSub }}>
        One row per pipeline run, for auditing an unattended night.
      </p>
      <Panel menu={false}>
        <DataTable
          empty="No runs recorded yet."
          rowKey={(r) => r.id}
          columns={[
            { key: 'id', label: 'ID', render: (r) => <span className="font-mono text-xs">{r.id}</span> },
            { key: 'mode', label: 'Mode', render: (r) => <StatusPill label={r.mode} /> },
            { key: 'started', label: 'Started', render: (r) => r.started_at },
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
