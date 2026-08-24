import React from 'react'
import {
  Home, Briefcase, ListChecks, UserRound, Globe, Filter, History, FileText,
  Trophy, Search, Download, Info, Settings,
} from 'lucide-react'
import { C } from './tokens.js'
import { Dropdown, useToast } from './components.jsx'

// ANALYTICS is the set someone opens constantly -- it becomes the top pill
// switcher. RESOURCES is lower-frequency -- it becomes the icon rail, each
// item named only on hover, the way the reference treats its own rail.
const NAV_ANALYTICS = [
  { href: '/', label: 'Dashboard', icon: Home },
  { href: '/jobs', label: 'Jobs', icon: Briefcase },
  { href: '/reach', label: 'Reach', icon: Globe },
  { href: '/funnel', label: 'Funnel', icon: Filter },
]

const NAV_RESOURCES = [
  { href: '/queue', label: 'Queue', icon: ListChecks, badgeKey: 'queued' },
  { href: '/profile', label: 'Profile', icon: UserRound },
  { href: '/runs', label: 'Runs', icon: History },
  { href: '/answers', label: 'Answers', icon: FileText },
  { href: '/competitions', label: 'Competitions', icon: Trophy },
]

function RailIcon({ href, label, icon: Icon, active, badge }) {
  return (
    <div className="relative group">
      <a
        href={href}
        aria-label={label}
        className="icon-btn focus-ring relative flex items-center justify-center h-10 w-10 rounded-xl"
        style={{
          background: active ? C.limeDim : 'transparent',
          color: active ? C.lime : C.textSub,
        }}
      >
        <Icon size={18} />
        {badge != null && (
          <span
            className="absolute -top-1 -right-1 font-semibold rounded-full flex items-center justify-center"
            style={{ background: C.lime, color: C.onLime, fontSize: '9px', minWidth: '15px', height: '15px', padding: '0 3px' }}
          >
            {badge}
          </span>
        )}
      </a>
      <span
        className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 whitespace-nowrap px-2 py-1 rounded-md text-xs font-medium opacity-0 group-hover:opacity-100 transition-opacity z-30"
        style={{ background: C.panelAlt, border: `1px solid ${C.border}`, color: C.text }}
      >
        {label}
      </span>
    </div>
  )
}

export default function NavShell({ route, title, subtitle, nav = {}, children }) {
  const [toast, showToast] = useToast()
  const isActive = (href) => href.slice(1) === route || (href === '/' && route === '')

  return (
    <div
      className="dashboard-root w-full min-h-screen flex"
      style={{ background: C.bg, color: C.text }}
    >
      {/* Icon rail */}
      <aside
        className="hidden lg:flex w-[68px] flex-shrink-0 flex-col items-center justify-between py-5"
        style={{ borderRight: `1px solid ${C.border}` }}
      >
        <div className="flex flex-col items-center gap-2">
          <div
            className="h-9 w-9 rounded-xl flex items-center justify-center mb-3"
            style={{ background: C.lime }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M4 20L14 4L20 14L10 20" stroke={C.onLime} strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          {NAV_RESOURCES.map((item) => (
            <RailIcon
              key={item.href}
              href={item.href}
              label={item.label}
              icon={item.icon}
              active={isActive(item.href)}
              badge={item.badgeKey ? nav[item.badgeKey] : undefined}
            />
          ))}
        </div>

        <div className="flex flex-col items-center gap-2">
          <RailIcon href="#" label="Help & Info" icon={Info} active={false} />
          <RailIcon href="/profile" label="Settings" icon={Settings} active={false} />
        </div>
      </aside>

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0">
        <header
          className="min-h-16 flex flex-wrap items-center justify-between gap-3 px-6 py-3 flex-shrink-0 sticky top-0 z-10"
          style={{ borderBottom: `1px solid ${C.border}`, background: C.bg }}
        >
          <div className="flex items-center gap-5">
            <div className="hidden xl:block pr-1">
              <div className="text-sm font-semibold truncate">{title}</div>
              <div className="text-[11px] truncate" style={{ color: C.textSub }}>{subtitle || 'Last 12 Months'}</div>
            </div>

            <nav
              className="flex items-center gap-1 p-1 rounded-full"
              style={{ background: C.panel, border: `1px solid ${C.border}` }}
            >
              {NAV_ANALYTICS.map((item) => {
                const Icon = item.icon
                const active = isActive(item.href)
                return (
                  <a
                    key={item.href}
                    href={item.href}
                    className="nav-pill focus-ring flex items-center gap-1.5 px-3 h-8 rounded-full text-xs font-semibold transition-colors"
                    style={{
                      background: active ? C.lime : 'transparent',
                      color: active ? C.onLime : C.textSub,
                    }}
                  >
                    <Icon size={14} />
                    <span className="hidden md:inline">{item.label}</span>
                  </a>
                )
              })}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden lg:flex items-center gap-2 rounded-full px-3 h-9 w-48" style={{ background: C.panel, border: `1px solid ${C.border}` }}>
              <Search size={14} style={{ color: C.textMute }} />
              <input
                type="text"
                placeholder="Search"
                className="focus-ring bg-transparent outline-none text-xs flex-1"
                style={{ color: C.text }}
              />
              <span className="px-1 rounded" style={{ color: C.textMute, border: `1px solid ${C.border}`, fontSize: '10px' }}>
                &#8984; K
              </span>
            </div>

            <Dropdown label="Year to Date" options={['This Month', 'Last Month', 'Last 3 Months', 'Last 12 Months', 'Year to Date']} />
            <button
              type="button"
              onClick={() => showToast('Summary generated')}
              className="btn-outline focus-ring hidden md:flex items-center gap-2 px-3 h-9 rounded-full text-xs font-semibold"
              style={{ border: `1px solid ${C.border}`, color: C.text }}
            >
              <FileText size={14} /> Summary
            </button>
            <button
              type="button"
              onClick={() => showToast('Download started')}
              className="btn-primary focus-ring flex items-center gap-2 px-3 h-9 rounded-full text-xs font-semibold"
              style={{ background: C.lime, color: C.onLime }}
            >
              <Download size={14} /> Download
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>

      {toast && (
        <div
          className="fixed bottom-6 right-6 px-4 py-3 rounded-xl text-sm font-medium shadow-lg z-50"
          style={{ background: C.panelAlt, border: `1px solid ${C.border}`, color: C.text }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
