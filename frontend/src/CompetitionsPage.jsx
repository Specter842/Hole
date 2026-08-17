import React from 'react'
import { C } from './tokens.js'
import { Panel, PostForm, TextField, TextAreaField, DeleteButton, Empty } from './components.jsx'

// Ported from jobsearch/web/pages.py's competitions_page() -- hackathons,
// case competitions, finance competitions, newest first. Real POST forms
// carry the CSRF token straight through to /competitions/add and
// /competitions/<id>/delete.

const CATEGORY_LABEL = {
  hackathon: 'Hackathon',
  case_competition: 'Case Competition',
  finance_competition: 'Finance Competition',
  other: 'Other',
}

export default function CompetitionsPage({ data }) {
  const { competitions, categories, token } = data

  return (
    <>
      <p className="text-sm mb-8 max-w-2xl" style={{ color: C.textSub }}>
        Hackathons, case competitions, and finance competitions -- entered here as they happen.
      </p>

      <Panel title="Add a competition" className="mb-6">
        <PostForm action="/competitions/add" token={token} submitLabel="Add competition">
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="name" label="Name" placeholder="MHacks 2026" />
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: C.textSub }}>
                Category
              </span>
              <select
                name="category"
                defaultValue={categories[0]?.value}
                className="rounded-lg px-3 py-2.5 text-sm focus-ring"
                style={{ background: 'rgba(255,255,255,.04)', border: `1px solid ${C.border}`, color: C.text }}
              >
                {categories.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </label>
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="result" label="Result (optional)" placeholder="Winner, Finalist, Participant..." />
            <TextField name="period" label="When" placeholder="e.g. 2026-09" />
          </div>
          <TextAreaField name="description" label="Description" placeholder="What it was, what you built" />
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="tech" label="Tech (comma separated, optional)" placeholder="Python, React" />
            <TextField name="url" label="Link (optional)" placeholder="https://..." />
          </div>
        </PostForm>
      </Panel>

      <Panel title={`Entries (${competitions.length})`} menu={false}>
        {competitions.length === 0 ? (
          <Empty>Nothing entered yet.</Empty>
        ) : (
          <div className="flex flex-col gap-4">
            {competitions.map((c) => (
              <div key={c.id} className="flex items-start justify-between gap-4 pb-4" style={{ borderBottom: `1px solid ${C.border}` }}>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold" style={{ color: C.text }}>{c.name}</span>
                    <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: C.teal }}>
                      {CATEGORY_LABEL[c.category] || c.category}
                    </span>
                    {c.result && (
                      <span className="text-xs" style={{ color: C.orange }}>{c.result}</span>
                    )}
                  </div>
                  {c.period && (
                    <div className="text-xs mt-0.5" style={{ color: C.textMute }}>{c.period}</div>
                  )}
                  {c.description && (
                    <div className="text-sm mt-1" style={{ color: C.textSub }}>{c.description}</div>
                  )}
                  {c.tech && (
                    <div className="text-xs mt-1 font-mono" style={{ color: C.textMute }}>{c.tech}</div>
                  )}
                  {c.url && (
                    <a href={c.url} target="_blank" rel="noreferrer" className="text-xs mt-1 inline-block" style={{ color: C.teal }}>
                      {c.url}
                    </a>
                  )}
                </div>
                <DeleteButton action={`/competitions/${c.id}/delete`} token={token} confirm={`Delete "${c.name}"? This cannot be undone.`} />
              </div>
            ))}
          </div>
        )}
      </Panel>
    </>
  )
}
