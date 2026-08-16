import React from 'react'
import { C } from './tokens.js'
import { Panel, DataTable, ActionButton, NoticeBlock } from './components.jsx'

// Ported from jobsearch/web/pages.py's review() -- rows a model extracted,
// awaiting human confirmation.

export default function ReviewPage({ data }) {
  const { sections, token } = data
  if (!sections.length) {
    return <NoticeBlock text="Nothing awaiting review. Every row is confirmed." />
  }
  return (
    <>
      {sections.map((section) => (
        <Panel key={section.name} title={`${section.name} (${section.rows.length})`} className="mb-6" menu={false}>
          <DataTable
            rowKey={(r) => r.id}
            columns={[
              { key: 'id', label: 'ID', render: (r) => <span className="font-mono text-xs">{r.id}</span> },
              { key: 'what', label: 'What', render: (r) => r.label },
              {
                key: 'confirm',
                label: '',
                render: (r) => (
                  <ActionButton action={`/review/${section.name}/${r.id}/verify`} token={token} label="Confirm" />
                ),
              },
            ]}
            rows={section.rows}
          />
        </Panel>
      ))}
    </>
  )
}
