import React from 'react'
import { C } from './tokens.js'
import { Panel, PostForm, TextField, TextAreaField, DeleteButton, Empty, Avatar } from './components.jsx'

// Ported from jobsearch/web/pages.py's competitions_page(). Two kinds of row
// share this table and this page keeps them apart: things already done (typed
// in, carry a `result`) and things still open (found by
// sourcing/competitions.py, carry a deadline and tracks).

const CATEGORY_LABEL = {
  hackathon: 'Hackathon',
  case_competition: 'Case Competition',
  finance_competition: 'Finance Competition',
  other: 'Other',
}

// A deadline is the one field on this page that decays -- it is worth nothing
// the day after it passes, so it gets colour rather than sitting in grey.
function deadlineTone(deadline) {
  if (!deadline) return null
  const when = Date.parse(deadline)
  if (Number.isNaN(when)) return { color: C.textMute, label: deadline }
  const days = Math.ceil((when - Date.now()) / 86400000)
  if (days < 0) return { color: C.textMute, label: `${deadline} -- closed` }
  if (days <= 7) return { color: C.red, label: `${deadline} -- ${days}d left` }
  if (days <= 21) return { color: C.yellow, label: `${deadline} -- ${days}d left` }
  return { color: C.lime, label: deadline }
}

function Tracks({ tracks }) {
  if (!tracks) return null
  const list = tracks.split(',').map((t) => t.trim()).filter(Boolean)
  if (!list.length) return null
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {list.map((t) => (
        <span
          key={t}
          className="text-[10px] font-medium px-1.5 py-0.5 rounded"
          style={{ background: C.panelAlt, color: C.textSub, border: `1px solid ${C.border}` }}
        >
          {t}
        </span>
      ))}
    </div>
  )
}

function Entry({ c, token }) {
  const due = deadlineTone(c.deadline)
  return (
    <div
      className="flex items-start justify-between gap-4 pb-4"
      style={{ borderBottom: `1px solid ${C.border}` }}
    >
      <div className="min-w-0 flex gap-3">
      <Avatar name={c.name} />
      <div className="min-w-0">
        <div className="flex items-center flex-wrap gap-2">
          <span className="text-sm font-semibold" style={{ color: C.text }}>{c.name}</span>
          <span
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: C.teal }}
          >
            {CATEGORY_LABEL[c.category] || c.category}
          </span>
          {c.result && <span className="text-xs" style={{ color: C.lime }}>{c.result}</span>}
        </div>

        {due && (
          <div className="text-xs mt-1 font-medium" style={{ color: due.color }}>
            {due.label}
          </div>
        )}
        {c.period && !due && (
          <div className="text-xs mt-0.5" style={{ color: C.textMute }}>{c.period}</div>
        )}
        {c.team_size && (
          <div className="text-xs mt-0.5" style={{ color: C.textMute }}>Team: {c.team_size}</div>
        )}
        {c.description && (
          <div className="text-sm mt-1" style={{ color: C.textSub }}>{c.description}</div>
        )}

        <Tracks tracks={c.tracks} />

        {c.tech && (
          <div className="text-xs mt-1 font-mono" style={{ color: C.textMute }}>{c.tech}</div>
        )}

        <div className="flex flex-wrap items-center gap-3 mt-1.5">
          {c.apply_url && (
            <a
              href={c.apply_url}
              target="_blank"
              rel="noreferrer"
              className="link-teal text-xs font-medium"
              style={{ color: C.teal }}
            >
              Apply &rarr;
            </a>
          )}
          {c.url && c.url !== c.apply_url && (
            <a
              href={c.url}
              target="_blank"
              rel="noreferrer"
              className="link-teal text-xs"
              style={{ color: C.textMute }}
            >
              details
            </a>
          )}
          {c.discovery_source && (
            <span className="text-[10px] uppercase tracking-wide" style={{ color: C.textMute }}>
              via {c.discovery_source}
            </span>
          )}
        </div>
      </div>
      </div>

      <DeleteButton
        action={`/competitions/${c.id}/delete`}
        token={token}
        confirm={`Delete "${c.name}"? This cannot be undone.`}
      />
    </div>
  )
}

export default function CompetitionsPage({ data }) {
  const { competitions, categories, token } = data

  // `status` is set by the scraper; anything hand-entered defaults to "entered".
  const discovered = competitions.filter((c) => c.status === 'discovered')
  const entered = competitions.filter((c) => c.status !== 'discovered')

  return (
    <>
      <p className="text-sm mb-8 max-w-2xl" style={{ color: C.textSub }}>
        Entered here as they happen, and found automatically by{' '}
        <code className="font-mono text-xs">competitions discover</code>.
      </p>

      <Panel title="Add a competition" className="mb-6">
        <PostForm action="/competitions/add" token={token} submitLabel="Add competition">
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="name" label="Name" placeholder="MHacks 2026" />
            <label className="flex flex-col gap-1.5 text-sm">
              <span
                className="text-[11px] font-semibold uppercase tracking-wide"
                style={{ color: C.textSub }}
              >
                Category
              </span>
              <select
                name="category"
                defaultValue={categories[0]?.value}
                className="rounded-lg px-3 py-2.5 text-sm focus-ring"
                style={{
                  background: 'rgba(255,255,255,.04)',
                  border: `1px solid ${C.border}`,
                  color: C.text,
                }}
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
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="deadline" label="Deadline (optional)" placeholder="Oct 01, 2026" />
            <TextField name="team_size" label="Team size (optional)" placeholder="2-4" />
          </div>
          <TextAreaField name="description" label="Description" placeholder="What it was, what you built" />
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="tracks" label="Tracks (comma separated, optional)" placeholder="AI, Fintech" />
            <TextField name="tech" label="Tech (comma separated, optional)" placeholder="Python, React" />
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="url" label="Link (optional)" placeholder="https://..." />
            <TextField name="apply_url" label="Apply link (optional)" placeholder="https://..." />
          </div>
        </PostForm>
      </Panel>

      {discovered.length > 0 && (
        <Panel title={`Open opportunities (${discovered.length})`} menu={false} className="mb-6">
          <div className="flex flex-col gap-4">
            {discovered.map((c) => <Entry key={c.id} c={c} token={token} />)}
          </div>
        </Panel>
      )}

      <Panel title={`Entered (${entered.length})`} menu={false}>
        {entered.length === 0 ? (
          <Empty>Nothing entered yet.</Empty>
        ) : (
          <div className="flex flex-col gap-4">
            {entered.map((c) => <Entry key={c.id} c={c} token={token} />)}
          </div>
        )}
      </Panel>
    </>
  )
}
