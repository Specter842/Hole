import React from 'react'
import {
  Home, Briefcase, ListChecks, UserRound, Globe, Filter, History, FileText,
  Search, Download, Info, Settings,
} from 'lucide-react'
import { C } from './tokens.js'
import { Dropdown, useToast } from './components.jsx'

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

export default function NavShell({ route, title, subtitle, nav = {}, children }) {
  const [toast, showToast] = useToast()

  return (
    <div
      className="dashboard-root w-full min-h-screen flex"
      style={{
        background: C.bg,
        color: C.text,
      }}
    >
      {/* Sidebar */}
      <aside
        className="hidden lg:flex w-60 flex-shrink-0 flex-col justify-between py-5 px-4"
        style={{ borderRight: `1px solid ${C.border}` }}
      >
        <div>
          <div className="flex items-center gap-2 px-2 mb-6">
            <div className="h-6 w-6 rounded flex items-center justify-center" style={{ background: C.text }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M4 20L14 4L20 14L10 20" stroke="#0A0A0B" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <span className="font-bold text-sm tracking-tight">Hole</span>
          </div>

          <div className="font-semibold tracking-wide mb-2 px-2 mt-1" style={{ color: C.textMute, fontSize: '11px' }}>
            ANALYTICS
          </div>
          <nav className="space-y-1 mb-5">
            {NAV_ANALYTICS.map((item) => {
              const Icon = item.icon
              const isActive = item.href.slice(1) === route || (item.href === '/' && route === '')
              return (
                <a
                  key={item.href}
                  href={item.href}
                  className="nav-btn focus-ring w-full flex items-center justify-between px-2 py-2 rounded-lg text-sm"
                  style={{
                    background: isActive ? C.panelAlt : 'transparent',
                    borderLeft: isActive ? `3px solid ${C.orange}` : '3px solid transparent',
                    color: isActive ? C.text : C.textSub,
                  }}
                >
                  <span className="flex items-center gap-2">
                    <Icon size={16} />
                    {item.label}
                  </span>
                </a>
              )
            })}
          </nav>

          <div className="font-semibold tracking-wide mb-2 px-2" style={{ color: C.textMute, fontSize: '11px' }}>
            RESOURCES
          </div>
          <nav className="space-y-1">
            {NAV_RESOURCES.map((item) => {
              const Icon = item.icon
              const isActive = item.href.slice(1) === route || (item.href === '/' && route === '')
              const badge = item.badgeKey ? nav[item.badgeKey] : undefined
              return (
                <a
                  key={item.href}
                  href={item.href}
                  className="nav-btn focus-ring w-full flex items-center justify-between px-2 py-2 rounded-lg text-sm"
                  style={{ color: isActive ? C.text : C.textSub, background: isActive ? C.panelAlt : 'transparent' }}
                >
                  <span className="flex items-center gap-2">
                    <Icon size={16} />
                    {item.label}
                  </span>
                  {badge != null && (
                    <span
                      className="font-semibold rounded-full flex items-center justify-center"
                      style={{ background: C.orange, color: '#fff', fontSize: '10px', minWidth: '16px', height: '16px', padding: '0 4px' }}
                    >
                      {badge}
                    </span>
                  )}
                </a>
              )
            })}
          </nav>
        </div>

        <div className="space-y-1">
          <a href="#" className="nav-btn focus-ring w-full flex items-center gap-2 px-2 py-2 rounded-lg text-sm" style={{ color: C.textSub }}>
            <Info size={16} /> Help & Info
          </a>
          <a href="/profile" className="nav-btn focus-ring w-full flex items-center gap-2 px-2 py-2 rounded-lg text-sm" style={{ color: C.textSub }}>
            <Settings size={16} /> Settings
          </a>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex-1 flex flex-col min-w-0">
        <header
          className="h-16 flex items-center justify-between px-6 flex-shrink-0 sticky top-0 z-10"
          style={{ borderBottom: `1px solid ${C.border}`, background: C.bg }}
        >
          <div>
            <div className="text-base font-semibold truncate">{title}</div>
            <div className="text-xs truncate" style={{ color: C.textSub }}>{subtitle || 'Last 12 Months'}</div>
          </div>

          <div className="hidden lg:flex items-center gap-2 rounded-lg px-3 h-9 w-48" style={{ background: C.panel, border: `1px solid ${C.border}` }}>
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

          <div className="flex items-center gap-3">
            <Dropdown label="Year to Date" options={['This Month', 'Last Month', 'Last 3 Months', 'Last 12 Months', 'Year to Date']} />
            <button
              type="button"
              onClick={() => showToast('Summary generated')}
              className="btn-outline focus-ring flex items-center gap-2 px-3 h-9 rounded-lg text-xs font-semibold"
              style={{ border: `1px solid ${C.border}`, color: C.text }}
            >
              <FileText size={14} /> Summary
            </button>
            <button
              type="button"
              onClick={() => showToast('Download started')}
              className="btn-primary focus-ring flex items-center gap-2 px-3 h-9 rounded-lg text-xs font-semibold"
              style={{ background: C.orange, color: '#fff' }}
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
          className="fixed bottom-6 right-6 px-4 py-3 rounded-lg text-sm font-medium shadow-lg z-50"
          style={{ background: C.panelAlt, border: `1px solid ${C.border}`, color: C.text }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
