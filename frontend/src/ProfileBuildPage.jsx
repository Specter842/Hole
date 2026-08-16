import React from 'react'
import { C } from './tokens.js'
import { Panel, PostForm, TextField, TextAreaField, SelectField, DeleteButton, StatusPill, NoticeBlock } from './components.jsx'

// Ported from jobsearch/web/pages.py's profile_build() -- positions,
// education, projects, certifications, skills, each a list of cards plus
// an inline add-form that posts real mutations. This is the one page that
// genuinely writes to the database from the browser, so every add-form is
// a real <form method="post"> carrying the session token straight to the
// same /profile/<entity>/add routes server.py already serves.

function Details({ summary, children }) {
  const [open, setOpen] = React.useState(false)
  return (
    <div className="mt-4">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-[11px] font-semibold uppercase tracking-wide focus-ring"
        style={{ color: C.textMute }}
      >
        {open ? '−' : '+'} {summary}
      </button>
      {open && <div className="mt-4">{children}</div>}
    </div>
  )
}

export default function ProfileBuildPage({ data }) {
  const {
    empty, counts, positions, education, projects, certifications,
    evidenced_skills, unevidenced_skills, token,
  } = data

  return (
    <>
      <p className="text-sm mb-6 max-w-2xl" style={{ color: C.textSub }}>
        Everything a resume is built from. Nothing here is generated -- tailoring selects
        from these rows and writes prose for them, it never adds a fact that is not on this
        page.
      </p>

      {empty && (
        <NoticeBlock
          tone="warn"
          text="No positions yet. Add one below, then add the things you did there -- an accomplishment has to belong to a position, project, or degree."
        />
      )}

      <h2 className="text-lg font-bold mt-2 mb-4" style={{ color: C.text }}>Positions</h2>
      {positions.map((p) => (
        <Panel key={p.id} className="mb-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-base font-semibold" style={{ color: C.text }}>
                {p.title}
                {p.organization && <span style={{ color: C.textMute }}> &middot; {p.organization}</span>}
              </div>
              <div className="text-xs font-mono mt-1" style={{ color: C.textMute }}>
                {p.dates}{p.location && <> &middot; {p.location}</>}
              </div>
            </div>
            <DeleteButton
              action={`/profile/experience/${p.id}/delete`} token={token}
              confirm="Delete this position and everything under it? This cannot be undone."
            />
          </div>
          {p.achievements.length ? (
            <ul className="mt-4 flex flex-col gap-3">
              {p.achievements.map((a) => (
                <li key={a.id} className="flex items-start justify-between gap-4 pt-3" style={{ borderTop: `1px solid ${C.border}` }}>
                  <div>
                    <div className="text-sm font-medium" style={{ color: C.text }}>{a.title}</div>
                    {a.detail && <div className="text-sm mt-1" style={{ color: C.textMute }}>{a.detail}</div>}
                    {a.impact && <div className="text-xs font-mono mt-1" style={{ color: C.teal }}>{a.impact}</div>}
                  </div>
                  <DeleteButton
                    action={`/profile/achievement/${a.id}/delete`} token={token}
                    confirm="Delete this accomplishment? This cannot be undone."
                  />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm mt-3" style={{ color: C.textMute }}>
              No accomplishments yet. These are what a resume is actually made of.
            </p>
          )}
          <Details summary="Add accomplishment">
            <PostForm action="/profile/achievement/add" token={token} submitLabel="Add accomplishment">
              <TextField name="experience_id" defaultValue={p.id} hidden />
              <div className="grid sm:grid-cols-2 gap-4">
                <TextField name="title" label="What you did" placeholder="Rebuilt the checkout API" />
                <TextField
                  name="impact" label="Measurable result (optional)" placeholder="cut p95 latency 40%"
                  hint="Only a number you can point at. Invented metrics are what grounding catches."
                />
              </div>
              <TextAreaField name="description" label="Detail" rows={2} placeholder="What the work was, in a sentence or two." />
              <TextField
                name="skills" label="Skills used (comma separated)" placeholder="Python, PostgreSQL"
                hint="Each becomes evidence that you have used that skill."
              />
            </PostForm>
          </Details>
        </Panel>
      ))}

      <Panel title="Add a position" className="mb-8">
        <PostForm action="/profile/experience/add" token={token} submitLabel="Add position">
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="title" label="Title" placeholder="Senior Software Engineer" />
            <TextField name="org" label="Company" placeholder="Acme Corp" />
            <TextField name="start" label="Started" placeholder="2021-03" />
            <TextField name="end" label="Ended" placeholder="leave blank if current" />
            <TextField name="location" label="Location" placeholder="Austin, TX" />
            <SelectField
              name="type" label="Employment type" defaultValue="full-time"
              options={['full-time', 'part-time', 'contract', 'internship', 'freelance']}
            />
          </div>
          <TextField name="skills" label="Skills (comma separated)" placeholder="Python, AWS" />
        </PostForm>
      </Panel>

      <h2 className="text-lg font-bold mb-4" style={{ color: C.text }}>Education</h2>
      {education.map((e) => (
        <Panel key={e.id} className="mb-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-base font-semibold" style={{ color: C.text }}>
                {e.degree}
                {e.organization && <span style={{ color: C.textMute }}> &middot; {e.organization}</span>}
              </div>
              <div className="text-xs font-mono mt-1" style={{ color: C.textMute }}>
                {e.field_of_study} {e.dates}
              </div>
            </div>
            <DeleteButton action={`/profile/education/${e.id}/delete`} token={token} confirm="Delete this degree? This cannot be undone." />
          </div>
        </Panel>
      ))}
      <Panel title="Add education" className="mb-8">
        <PostForm action="/profile/education/add" token={token} submitLabel="Add education">
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="title" label="Degree" placeholder="BS Computer Science" />
            <TextField name="org" label="School" placeholder="University of Texas" />
            <TextField name="field" label="Field of study" placeholder="Computer Science" />
            <TextField name="start" label="Started" placeholder="2015" />
            <TextField name="end" label="Finished" placeholder="2019" />
          </div>
        </PostForm>
      </Panel>

      <h2 className="text-lg font-bold mb-4" style={{ color: C.text }}>Projects</h2>
      {projects.map((p) => (
        <Panel key={p.id} className="mb-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-base font-semibold" style={{ color: C.text }}>{p.name}</div>
              <div className="text-sm mt-1" style={{ color: C.textMute }}>{p.description}</div>
            </div>
            <DeleteButton action={`/profile/project/${p.id}/delete`} token={token} confirm="Delete this project? This cannot be undone." />
          </div>
        </Panel>
      ))}
      <Panel title="Add a project" className="mb-8">
        <PostForm action="/profile/project/add" token={token} submitLabel="Add project">
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="title" label="Name" placeholder="Open-source scheduler" />
            <TextField name="role" label="Your role" placeholder="Creator" />
            <TextField name="url" label="Link" placeholder="https://github.com/..." />
            <TextField name="skills" label="Skills (comma separated)" placeholder="Go, Kubernetes" />
          </div>
          <TextAreaField name="description" label="What it is" rows={2} />
        </PostForm>
      </Panel>

      <h2 className="text-lg font-bold mb-4" style={{ color: C.text }}>Certifications</h2>
      {certifications.map((c) => (
        <Panel key={c.id} className="mb-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-base font-semibold" style={{ color: C.text }}>
                {c.name}
                {c.issuer && <span style={{ color: C.textMute }}> &middot; {c.issuer}</span>}
              </div>
              <div className="text-xs font-mono mt-1" style={{ color: C.textMute }}>{c.issue_date}</div>
            </div>
            <DeleteButton action={`/profile/certification/${c.id}/delete`} token={token} confirm="Delete this certification? This cannot be undone." />
          </div>
        </Panel>
      ))}
      <Panel title="Add a certification" className="mb-8">
        <PostForm action="/profile/certification/add" token={token} submitLabel="Add certification">
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="title" label="Name" placeholder="AWS Solutions Architect" />
            <TextField name="org" label="Issuer" placeholder="Amazon Web Services" />
            <TextField name="start" label="Issued" placeholder="2024-06" />
            <TextField name="url" label="Credential link" placeholder="https://..." />
          </div>
        </PostForm>
      </Panel>

      <h2 className="text-lg font-bold mb-4" style={{ color: C.text }}>Skills</h2>
      <p className="text-sm mb-4" style={{ color: C.textSub }}>
        {evidenced_skills.length} with evidence, {unevidenced_skills.length} without. A skill
        with no evidence never reaches a resume, however loudly a posting asks for it -- attach
        it to a position or accomplishment above to make it usable.
      </p>
      {evidenced_skills.length > 0 && (
        <Panel className="mb-4">
          <div className="flex flex-wrap gap-2">
            {evidenced_skills.map((s, i) => (
              <StatusPill key={i} label={`${s.name} · ${s.evidence_count}`} tone="good" />
            ))}
          </div>
        </Panel>
      )}
      {unevidenced_skills.length > 0 && (
        <NoticeBlock tone="warn" text="These are claimed but nothing proves them, so they stay off every resume:" items={unevidenced_skills} />
      )}
      <Panel title="Add a skill" className="mb-8">
        <p className="text-sm mb-5" style={{ color: C.textMute }}>
          Adding a skill here records the claim. It only becomes usable once something
          demonstrates it -- list it on a position or accomplishment above, or run{' '}
          <span className="font-mono">jobsearch link</span> to scan your records for it.
        </p>
        <PostForm action="/profile/skill/add" token={token} submitLabel="Add skill">
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="name" label="Skill" placeholder="PostgreSQL" />
            <SelectField name="proficiency" label="Proficiency" defaultValue="working" options={['familiar', 'working', 'advanced', 'expert']} />
          </div>
        </PostForm>
      </Panel>

      <p className="text-sm" style={{ color: C.textMute }}>
        {counts.experiences || 0} positions &middot; {counts.accomplishments || 0} accomplishments &middot; {counts.skills || 0} skills
      </p>
    </>
  )
}
