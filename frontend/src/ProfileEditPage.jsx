import React from 'react'
import { C } from './tokens.js'
import { Panel, PostForm, TextField, TextAreaField, DeleteButton, NoticeBlock } from './components.jsx'

// Ported from jobsearch/web/pages.py's profile_edit() -- every field a
// form might ask for, in one place. Real POST forms to /profile/save.

export default function ProfileEditPage({ data }) {
  const { fields, summary, missing, extra, token } = data

  return (
    <>
      <p className="text-sm mb-6 max-w-2xl" style={{ color: C.textSub }}>
        What gets typed into application forms. Anything blank here is a field an
        application can stop on.
      </p>

      {missing.length > 0 && <NoticeBlock tone="warn" text="Not filled in yet" items={missing} />}

      <Panel className="mb-6">
        <PostForm action="/profile/save" token={token} submitLabel="Save details">
          <div className="grid sm:grid-cols-2 gap-4">
            {fields.map((f) => (
              <TextField key={f.name} name={f.name} label={f.label} defaultValue={f.value} type={f.kind} hint={f.hint} />
            ))}
          </div>
          <TextAreaField
            name="summary" label="Summary" defaultValue={summary} rows={4}
            hint="A few lines about you. Used for tone, never copied verbatim."
          />
        </PostForm>
      </Panel>

      {extra.length > 0 && (
        <Panel title="Other details" className="mb-6">
          <div className="flex flex-col gap-4">
            {extra.map((item) => (
              <div key={item.key} className="flex items-start justify-between gap-4 pb-4" style={{ borderBottom: `1px solid ${C.border}` }}>
                <div>
                  <div className="font-mono text-xs" style={{ color: C.textSub }}>{item.key}</div>
                  <div className="text-sm mt-1" style={{ color: C.text }}>{item.value}</div>
                </div>
                <DeleteButton action={`/profile/attr/${item.key}/delete`} token={token} />
              </div>
            ))}
          </div>
        </Panel>
      )}

      <Panel title="Add anything else">
        <p className="text-sm mb-5" style={{ color: C.textMute }}>
          Pronouns, clearance level, salary floor, visa status -- anything a form might ask
          that has no box above.
        </p>
        <PostForm action="/profile/save" token={token} submitLabel="Add detail">
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField name="key" label="Name" placeholder="security_clearance" />
            <TextField name="value" label="Value" placeholder="Secret, active" />
          </div>
        </PostForm>
      </Panel>
    </>
  )
}
