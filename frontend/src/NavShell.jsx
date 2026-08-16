import React from 'react'
import {
  Home, Briefcase, ListChecks, UserRound, Globe, Filter, History, FileText,
  Search, ChevronDown, Download, Info, Settings,
} from 'lucide-react'
import { C } from './tokens.js'

// Ported from NAV_ANALYTICS/NAV_RESOURCES in estics-reach-dashboard.jsx, but
// pointed at this app's real routes. The reference's Alerts/Preferences/Docs/
// Changelog items have no literal equivalent here, so real pages were
// re-bucketed into the two sections instead: Dashboard/Jobs/Reach/Funnel read
// as "analytics" surfaces, Queue/Profile/Runs/Answers as "resources" -- the
// operational/reference pages behind the analytics.
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
]

function NavItem({ item, active, badge }) {
  const Icon = item.icon
  return (
    <a
      href={item.href}
      className="relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors focus-ring"
      style={{
        color: active ? C.text : C.textSub,
        background: active ? C.panelAlt : 'transparent',
      }}
    >
      {active && (
        <span
          className="absolute left-[-16px] top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-full"
          style={{ background: C.orange }}
        />
      )}
      <Icon size={17} style={{ color: active ? C.text : C.textMute }} />
      <span className="flex-1">{item.label}</span>
      {!!badge && (
        <span
          className="text-[10px] font-bold rounded-full min-w-[18px] h-[18px] px-1 flex items-center justify-center"
          style={{ background: C.orange, color: C.bg }}
        >
          {badge}
        </span>
      )}
    </a>
  )
}

function SectionLabel({ children }) {
  return (
    <div
      className="px-3 pt-5 pb-2 text-[10px] font-semibold uppercase tracking-wider"
      style={{ color: C.textMute }}
    >
      {children}
    </div>
  )
}

export default function NavShell({ route, title, subtitle, nav = {}, children }) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: C.bg }}>
      <header
        className="flex items-center gap-4 px-4 md:px-6 h-16 shrink-0"
        style={{ borderBottom: `1px solid ${C.border}` }}
      >
        <div className="flex items-center gap-2 w-60 shrink-0">
          <span
            className="inline-block w-2.5 h-2.5 rotate-45"
            style={{ background: C.orange }}
            aria-hidden="true"
          />
          <span className="text-sm font-bold tracking-tight" style={{ color: C.text }}>
            jobsearch
          </span>
        </div>

        <div className="flex-1 min-w-0">
          <div className="text-base md:text-lg font-bold tracking-tight truncate" style={{ color: C.text }}>
            {title}
          </div>
          {subtitle && (
            <div className="text-xs truncate" style={{ color: C.textMute }}>
              {subtitle}
            </div>
          )}
        </div>

        <div className="hidden lg:flex items-center gap-2">
          <label className="relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2"
              style={{ color: C.textMute }}
            />
            <input
              type="text"
              placeholder="Search"
              aria-label="Search"
              className="h-9 w-48 rounded-lg pl-9 pr-10 text-xs focus-ring"
              style={{ background: C.panel, border: `1px solid ${C.border}`, color: C.text }}
              readOnly
            />
            <span
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] px-1.5 py-0.5 rounded"
              style={{ color: C.textMute, background: C.panelAlt }}
            >
              &#8984;K
            </span>
          </label>
          <button
            type="button"
            className="flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-medium focus-ring"
            style={{ background: C.panel, border: `1px solid ${C.border}`, color: C.text }}
          >
            Year to Date
            <ChevronDown size={14} style={{ color: C.textSub }} />
          </button>
          <button
            type="button"
            className="flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-medium focus-ring"
            style={{ background: C.panel, border: `1px solid ${C.border}`, color: C.text }}
          >
            <Info size={14} style={{ color: C.textSub }} />
            Summary
          </button>
          <button
            type="button"
            className="flex items-center gap-1.5 h-9 px-3 rounded-lg text-xs font-semibold focus-ring"
            style={{ background: C.orange, color: '#1a0d05' }}
          >
            <Download size={14} />
            Download
          </button>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <aside
          className="hidden md:flex flex-col shrink-0 w-60 px-4 py-6 gap-1 overflow-y-auto"
          style={{ borderRight: `1px solid ${C.border}` }}
        >
          <SectionLabel>Analytics</SectionLabel>
          {NAV_ANALYTICS.map((item) => (
            <NavItem key={item.href} item={item} active={item.href.slice(1) === route} />
          ))}

          <SectionLabel>Resources</SectionLabel>
          {NAV_RESOURCES.map((item) => (
            <NavItem
              key={item.href}
              item={item}
              active={item.href.slice(1) === route}
              badge={item.badgeKey ? nav[item.badgeKey] : undefined}
            />
          ))}

          <div className="flex-1" />

          <div className="flex flex-col gap-1 pt-4" style={{ borderTop: `1px solid ${C.border}` }}>
            <a href="#" className="flex items-center gap-3 px-3 py-2 rounded-lg text-xs focus-ring" style={{ color: C.textSub }}>
              <Info size={15} style={{ color: C.textMute }} />
              Help &amp; Info
            </a>
            <a href="/profile" className="flex items-center gap-3 px-3 py-2 rounded-lg text-xs focus-ring" style={{ color: C.textSub }}>
              <Settings size={15} style={{ color: C.textMute }} />
              Settings
            </a>
          </div>
        </aside>
        <main className="flex-1 min-w-0 px-6 md:px-10 py-8 md:py-10 overflow-x-hidden">{children}</main>
      </div>
    </div>
  )
}
