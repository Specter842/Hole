import React from 'react'
import { createRoot } from 'react-dom/client'
import NavShell from './NavShell.jsx'
import DashboardPage from './DashboardPage.jsx'
import ReachPage from './ReachPage.jsx'
import FunnelPage from './FunnelPage.jsx'
import JobsPage from './JobsPage.jsx'
import QueuePage from './QueuePage.jsx'
import ProfilePage from './ProfilePage.jsx'
import ReviewPage from './ReviewPage.jsx'
import RunsPage from './RunsPage.jsx'
import AnswersPage from './AnswersPage.jsx'
import CompetitionsPage from './CompetitionsPage.jsx'
import ProfileEditPage from './ProfileEditPage.jsx'
import ProfileBuildPage from './ProfileBuildPage.jsx'
import './index.css'

// jobsearch/web/pages.py renders the mount point with `data-route` and
// `data-payload` attributes -- the route name (used for NavShell's active
// nav item) and the page's real data, queried straight out of the sqlite
// database, never mock data. Several pages share a route (e.g. `/jobs` and
// `/jobs/<id>` both use route 'jobs', so the Jobs nav item stays active on
// both) and are told apart by `data.page`, which every _react_page() call
// now sets. These travel as HTML attributes rather than an inline script
// with dynamic content, because this server's CSP allows inline scripts
// only by exact hash of a fixed, known body -- a per-request script tag
// would need a new hash every time and could not be allow-listed in
// advance.
const rootEl = document.getElementById('jobsearch-react-root')
const route = rootEl ? rootEl.dataset.route : ''
let data = {}
try {
  data = rootEl ? JSON.parse(rootEl.dataset.payload || '{}') : {}
} catch (e) {
  data = {}
}

const PAGE_META = {
  '': { title: 'Dashboard', subtitle: 'Profile, pipeline health, and where postings reach' },
  reach: { title: 'Reach', subtitle: 'Where postings come from, and where applications go' },
  funnel: { title: 'Funnel', subtitle: 'Where postings stop, on the way to being sent' },
  jobs: { title: 'Jobs', subtitle: 'Sourced postings, best fit first' },
  queue: { title: 'Queue', subtitle: 'Everything drafted, approved, or sent' },
  profile: { title: 'Profile', subtitle: 'The graph every resume is drawn from' },
  review: { title: 'Review', subtitle: 'Rows a model extracted, awaiting confirmation' },
  runs: { title: 'Runs', subtitle: 'One row per pipeline run' },
  answers: { title: 'Answers', subtitle: 'What forms fill from, and what is still missing' },
  competitions: { title: 'Competitions', subtitle: 'Hackathons, case competitions, finance competitions' },
}

// A page-specific title/subtitle overrides the route default -- e.g. a job
// detail page's title is the job itself, not "Jobs".
const PAGE_OVERRIDE = {
  job_detail: (d) => ({ title: `${d.job.title} @ ${d.job.company || ''}`.trim(), subtitle: '' }),
  application_detail: (d) => ({
    title: `${d.application.role || 'Application'} @ ${d.application.company || ''}`.trim(),
    subtitle: '',
  }),
  profile_edit: () => ({ title: 'Your details', subtitle: 'What gets typed into application forms' }),
  profile_build: () => ({ title: 'Your history', subtitle: 'Everything a resume is built from' }),
}

const PAGE_COMPONENTS = {
  jobs_list: JobsPage,
  job_detail: JobsPage,
  queue: QueuePage,
  application_detail: QueuePage,
  profile: ProfilePage,
  profile_edit: ProfileEditPage,
  profile_build: ProfileBuildPage,
  review: ReviewPage,
  runs: RunsPage,
  answers: AnswersPage,
  competitions: CompetitionsPage,
}

function App() {
  const meta = { ...(PAGE_META[route] || { title: 'Hole', subtitle: '' }) }
  if (data.page && PAGE_OVERRIDE[data.page]) {
    Object.assign(meta, PAGE_OVERRIDE[data.page](data))
  }

  let Page = DashboardPage
  if (data.page && PAGE_COMPONENTS[data.page]) {
    Page = PAGE_COMPONENTS[data.page]
  } else if (route === 'reach') {
    Page = ReachPage
  } else if (route === 'funnel') {
    Page = FunnelPage
  }

  return (
    <NavShell route={route} title={meta.title} subtitle={meta.subtitle} nav={data.nav || {}}>
      <Page data={data} />
    </NavShell>
  )
}

if (rootEl) {
  createRoot(rootEl).render(<App />)
}
