import React from 'react'
import {
  Home, Briefcase, ListChecks, UserRound, Globe, Filter, History, FileText,
  Trophy, Search, Download,
} from 'lucide-react'
import { C } from './tokens.js'
import { Dropdown, useToast } from './components.jsx'

// One flat list now -- a bottom bar doesn't have the rail's room for a
// "frequent vs. occasional" split, so all nine destinations sit together,
// ordered the way someone actually moves through the app.
const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: Home },
  { href: '/jobs', label: 'Jobs', icon: Briefcase },
  { href: '/queue', label: 'Queue', icon: ListChecks, badgeKey: 'queued' },
  { href: '/reach', label: 'Reach', icon: Globe },
  { href: '/funnel', label: 'Funnel', icon: Filter },
  { href: '/profile', label: 'Profile', icon: UserRound },
  { href: '/runs', label: 'Runs', icon: History },
  { href: '/answers', label: 'Answers', icon: FileText },
  { href: '/competitions', label: 'Competitions', icon: Trophy },
]

function BottomNavItem({ href, label, icon: Icon, active, badge }) {
  return (
    <a
      href={href}
      className="nav-pill focus-ring relative flex flex-col items-center justify-center gap-1 py-2 rounded-xl transition-colors flex-1 min-w-[64px]"
      style={{ color: active ? C.lime : C.textSub }}
    >
      <span
        className="relative flex items-center justify-center h-8 w-8 rounded-full"
        style={{ background: active ? C.limeDim : 'transparent' }}
      >
        <Icon size={17} />
        {badge != null && (
          <span
            className="absolute -top-1 -right-1 font-semibold rounded-full flex items-center justify-center"
            style={{ background: C.lime, color: C.onLime, fontSize: '9px', minWidth: '15px', height: '15px', padding: '0 3px' }}
          >
            {badge}
          </span>
        )}
      </span>
      <span className="text-[10px] font-medium leading-none whitespace-nowrap">{label}</span>
    </a>
  )
}

export default function NavShell({ route, title, subtitle, nav = {}, children }) {
  const [toast, showToast] = useToast()
  const isActive = (href) => href.slice(1) === route || (href === '/' && route === '')

  return (
    <div
      className="dashboard-root w-full min-h-screen flex flex-col"
      style={{ background: C.bg, color: C.text }}
    >
      <header
        className="min-h-16 flex flex-wrap items-center justify-between gap-3 px-6 py-3 flex-shrink-0 sticky top-0 z-10"
        style={{ borderBottom: `1px solid ${C.border}`, background: C.bg }}
      >
        <div className="flex items-center gap-3">
          <div
            className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{ background: C.lime }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M4 20L14 4L20 14L10 20" stroke={C.onLime} strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div>
            <div className="text-sm font-semibold truncate">{title}</div>
            <div className="text-[11px] truncate" style={{ color: C.textSub }}>{subtitle || 'Last 12 Months'}</div>
          </div>
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

      <main className="flex-1 overflow-auto p-6 pb-24">
        {children}
      </main>

      {/* Bottom nav */}
      <nav
        className="sticky bottom-0 flex items-stretch gap-1 px-3 py-2 flex-shrink-0 z-20 overflow-x-auto"
        style={{ background: C.panel, borderTop: `1px solid ${C.border}` }}
      >
        {NAV_ITEMS.map((item) => (
          <BottomNavItem
            key={item.href}
            href={item.href}
            label={item.label}
            icon={item.icon}
            active={isActive(item.href)}
            badge={item.badgeKey ? nav[item.badgeKey] : undefined}
          />
        ))}
      </nav>

      {toast && (
        <div
          className="fixed bottom-24 right-6 px-4 py-3 rounded-xl text-sm font-medium shadow-lg z-50"
          style={{ background: C.panelAlt, border: `1px solid ${C.border}`, color: C.text }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
