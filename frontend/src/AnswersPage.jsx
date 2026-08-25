import React from 'react'
import { C } from './tokens.js'
import { Panel, PostForm, TextField, TextAreaField, DeleteButton } from './components.jsx'

// Ported from jobsearch/web/pages.py's answers_page() -- the answer bank:
// what forms fill from, and what is still missing. Real POST forms carry
// the CSRF token straight through to /answers/add and /answers/<id>/delete.

export default function AnswersPage({ data }) {
  const { gaps, stored, suggestions, token } = data

  return (
    <>
      <p className="text-sm mb-8 max-w-2xl" style={{ color: C.textSub }}>
        Forms ask things a resume does not cover. Write each answer once here and applications
        fill from it. Nothing on this page is ever generated -- what you type is exactly what
        gets submitted.
      </p>

      {gaps.length > 0 && (
        <Panel title="Blocking your applications" className="mb-6">
          <p className="text-sm mb-5" style={{ color: C.textMute }}>
            These stopped a real application. Answer one and it is covered on every future
            posting that asks it.
          </p>
          <div className="flex flex-col gap-5">
            {gaps.map((gap, i) => (
              <div key={i} className="pb-5" style={{ borderBottom: i < gaps.length - 1 ? `1px solid ${C.border}` : 'none' }}>
                <div className="text-sm mb-3" style={{ color: C.text }}>
                  <b style={{ color: C.lime }}>{gap.seen_count}&times;</b> {gap.question}
                  {gap.company && <span style={{ color: C.textMute }}> &middot; {gap.company}</span>}
                </div>
                <PostForm action="/answers/add" token={token} submitLabel="Answer it">
                  <TextField name="pattern" defaultValue={gap.question.slice(0, 60)} placeholder="question to match" />
                  <TextField name="answer" placeholder="your answer" />
                </PostForm>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {stored.length > 0 && (
        <Panel title={`Stored (${stored.length})`} className="mb-6">
          <div className="flex flex-col gap-4">
            {stored.map((item) => (
              <div key={item.id} className="flex items-start justify-between gap-4 pb-4" style={{ borderBottom: `1px solid ${C.border}` }}>
                <div>
                  <div className="font-mono text-xs" style={{ color: C.textSub }}>
                    {item.pattern}
                    {item.company && <span style={{ color: C.textMute }}> &middot; {item.company}</span>}
                  </div>
                  <div className="text-sm mt-1" style={{ color: C.text }}>{item.answer}</div>
                </div>
                <DeleteButton action={`/answers/${item.id}/delete`} token={token} />
              </div>
            ))}
          </div>
        </Panel>
      )}

      {suggestions.length > 0 && (
        <Panel title="Common questions" className="mb-6">
          <p className="text-sm mb-5" style={{ color: C.textMute }}>
            Filling these in covers most application forms. Skip any that do not apply to you.
          </p>
          <div className="flex flex-col gap-5">
            {suggestions.map((s) => (
              <div key={s.pattern} className="pb-5" style={{ borderBottom: `1px solid ${C.border}` }}>
                <PostForm action="/answers/add" token={token} submitLabel="Save">
                  <TextField name="pattern" defaultValue={s.pattern} hidden />
                  <TextField name="answer" label={s.label} placeholder={s.hint} hint={s.hint} />
                </PostForm>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <Panel title="Add your own">
        <PostForm action="/answers/add" token={token} submitLabel="Add answer">
          <div className="grid sm:grid-cols-2 gap-4">
            <TextField
              name="pattern" label="Question contains" placeholder="visa sponsorship"
              hint="Matched against the form's question, case-insensitive."
            />
            <TextField
              name="company" label="Only for company (optional)" placeholder="Anthropic"
              hint="Leave blank to use for every employer."
            />
          </div>
          <TextAreaField name="answer" label="Answer" placeholder="Exactly what should be entered" />
        </PostForm>
      </Panel>
    </>
  )
}
