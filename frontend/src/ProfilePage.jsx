import React from 'react'
import { Briefcase, Award, FolderGit2, GraduationCap, Sparkles } from 'lucide-react'
import { C } from './tokens.js'
import { Panel, Empty, StatusPill, DataTable, NoticeBlock, MetricCard } from './components.jsx'

// Ported from jobsearch/web/pages.py's profile() -- the graph every resume
// is drawn from, read-only.

const COUNT_ICON = {
  experiences: Briefcase,
  achievements: Award,
  projects: FolderGit2,
  education: GraduationCap,
  skills: Sparkles,
}

export default function ProfilePage({ data }) {
  const { empty, counts, positions, projects, skills, unevidenced } = data

  return (
    <>
      {empty && <NoticeBlock tone="warn" text="The graph is empty. Import a LinkedIn export or a resume first." />}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        {['experiences', 'achievements', 'projects', 'education', 'skills'].map((key, i) => (
          <MetricCard key={key} label={key} value={counts[key] || 0} icon={COUNT_ICON[key]} tone={i} />
        ))}
      </div>

      {positions.length > 0 && (
        <Panel title="Positions" className="mb-6">
          <div className="flex flex-col gap-6">
            {positions.map((p, i) => (
              <div key={i} className="pb-5" style={{ borderBottom: i < positions.length - 1 ? `1px solid ${C.border}` : 'none' }}>
                <div className="text-base font-semibold" style={{ color: C.text }}>{p.label}</div>
                <div className="text-xs font-mono mt-0.5" style={{ color: C.textMute }}>{p.dates}</div>
                {p.achievements.length ? (
                  <ul className="mt-3 flex flex-col gap-2">
                    {p.achievements.map((a, j) => (
                      <li key={j} className="text-sm flex items-start gap-2" style={{ color: C.textSub }}>
                        <span>
                          {a.text}
                          {a.impact && <span className="ml-2 text-xs" style={{ color: C.textMute }}>({a.impact})</span>}
                        </span>
                        {!a.verified && <StatusPill label="unconfirmed" tone="warn" />}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-sm mt-2" style={{ color: C.textMute }}>No accomplishments recorded.</div>
                )}
              </div>
            ))}
          </div>
        </Panel>
      )}

      {projects.length > 0 && (
        <Panel title="Projects" className="mb-6">
          <div className="flex flex-col gap-4">
            {projects.map((p, i) => (
              <div key={i}>
                <div className="text-base font-semibold" style={{ color: C.text }}>{p.name}</div>
                <div className="text-sm mt-0.5" style={{ color: C.textMute }}>{p.description}</div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <Panel title="Skills" menu={false}>
        <DataTable
          empty="No skills recorded."
          rowKey={(s, i) => s.name + i}
          columns={[
            { key: 'skill', label: 'Skill', render: (s) => s.name },
            {
              key: 'evidence',
              label: 'Evidence',
              render: (s) =>
                s.evidence_count > 0 ? (
                  <StatusPill label={`${s.evidence_count} record(s)`} tone="good" />
                ) : (
                  <StatusPill label="none -- will never appear on a resume" tone="bad" />
                ),
            },
            { key: 'category', label: 'Category' },
          ]}
          rows={skills}
        />
      </Panel>

      {unevidenced.length > 0 && (
        <NoticeBlock
          tone="warn"
          text={`${unevidenced.length} skill(s) have no supporting record, so they are locked out of every resume:`}
          items={unevidenced}
        />
      )}
    </>
  )
}
