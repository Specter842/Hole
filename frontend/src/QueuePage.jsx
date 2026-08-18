import React from 'react'
import { C } from './tokens.js'
import { Panel, Empty, StatusPill, ScoreBar, DataTable, KV, ActionButton, NoticeBlock, BackLink } from './components.jsx'

// Ported from jobsearch/web/pages.py's queue()/application_detail().

function QueueListPage({ data }) {
  const { applications } = data
  return (
    <>
      <Panel menu={false}>
        <DataTable
          empty="Nothing drafted yet."
          rowKey={(a) => a.id}
          columns={[
            { key: 'id', label: 'ID', render: (a) => <a href={`/applications/${a.id}`} style={{ color: C.teal }}>#{a.id}</a> },
            { key: 'role', label: 'Role' },
            { key: 'company', label: 'Company' },
            { key: 'fit', label: 'Fit', render: (a) => <ScoreBar score={a.fit_score} /> },
            {
              key: 'grounding',
              label: 'Grounding',
              render: (a) => <StatusPill label={a.grounding_status} tone={a.grounding_clean ? 'good' : 'warn'} />,
            },
            { key: 'status', label: 'Status', render: (a) => <StatusPill label={a.status} tone={a.tone} /> },
            { key: 'channel', label: 'Channel' },
          ]}
          rows={applications}
        />
      </Panel>
    </>
  )
}

function ApplicationDetailPage({ data }) {
  const { application: a, reasons, documents, documents_missing, token } = data
  const status = (a.status || '').toLowerCase()
  return (
    <>
      <BackLink href="/queue" label="Back to Queue" />
      <Panel menu={false}>
        <KV
          items={[
            { label: 'Status', value: <StatusPill label={a.status} tone={a.tone} /> },
            { label: 'Fit score', value: <ScoreBar score={a.fit_score} /> },
            {
              label: 'Grounding',
              value: <StatusPill label={a.grounding_status} tone={a.grounding_clean ? 'good' : 'warn'} />,
            },
            { label: 'Channel', value: a.channel },
            { label: 'Source', value: a.source },
            {
              label: 'Posting',
              value: a.job_url && (
                <a href={a.job_url} target="_blank" rel="noreferrer noopener" style={{ color: C.teal }}>link</a>
              ),
            },
            { label: 'Bundle', value: a.resume_version && <span className="font-mono text-xs">{a.resume_version}</span> },
            { label: 'Approved', value: a.approved_at },
            { label: 'Sent', value: a.sent_date },
            { label: 'Dispatch error', value: a.dispatch_error && <span style={{ color: C.red }}>{a.dispatch_error}</span> },
          ]}
        />
      </Panel>

      {reasons && reasons.length > 0 && (
        <NoticeBlock tone="" text="Why the policy engine decided this:" items={reasons} />
      )}

      {status === 'drafted' && (
        <div className="flex gap-3 mt-6">
          <ActionButton action={`/applications/${a.id}/approve`} token={token} label="Approve" primary />
          <ActionButton action={`/applications/${a.id}/reject`} token={token} label="Reject" />
        </div>
      )}
      {status === 'approved' && (
        <NoticeBlock
          tone="warn"
          text="Approved. This tool does not send from the browser -- run the pipeline, or send it yourself from the bundle folder."
        />
      )}

      {documents_missing && (
        <NoticeBlock tone="warn" text="The generated documents are not on disk at the recorded path." />
      )}

      {Object.entries(documents || {}).map(([name, content]) => (
        <Panel key={name} title={name} className="mt-6">
          <pre className="whitespace-pre-wrap text-sm leading-relaxed font-mono" style={{ color: C.textSub }}>
            {content}
          </pre>
        </Panel>
      ))}
    </>
  )
}

export default function QueuePage({ data }) {
  if (data.page === 'application_detail') return <ApplicationDetailPage data={data} />
  return <QueueListPage data={data} />
}
