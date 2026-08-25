import React from 'react'
import {
  Home, Briefcase, ListChecks, UserRound, Globe, Filter, History, FileText,
  Trophy, Search, Download, Bell,
} from 'lucide-react'
import { C } from './tokens.js'
import { Dropdown, useToast, Avatar } from './components.jsx'

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

function NavPill({ href, label, icon: Icon, active, badge }) {
  return (
    <a
      href={href}
      className="nav-pill focus-ring relative flex items-center gap-1.5 px-3 h-9 rounded-full text-xs font-semibold transition-all"
      style={{
        background: active ? C.lime : 'transparent',
        color: active ? C.onLime : C.textSub,
        boxShadow: active ? `0 4px 16px -2px ${C.lime}66` : 'none',
      }}
    >
      <Icon size={14} />
      <span className="whitespace-nowrap">{label}</span>
      {badge != null && (
        <span
          className="absolute -top-1.5 -right-1.5 font-semibold rounded-full flex items-center justify-center"
          style={{
            background: active ? C.onLime : C.lime,
            color: active ? C.lime : C.onLime,
            fontSize: '9px', minWidth: '15px', height: '15px', padding: '0 3px',
          }}
        >
          {badge}
        </span>
      )}
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
      {/* Hairline accent -- the one spot of pure gradient in the whole UI,
          so the top edge of the app reads as designed, not just dark. */}
      <div className="h-[3px] flex-shrink-0" style={{ background: `linear-gradient(90deg, ${C.lime}, ${C.purple}, ${C.teal})` }} />

      <header
        className="flex flex-wrap items-center gap-4 px-6 py-3 flex-shrink-0 sticky top-0 z-20"
        style={{
          background: `linear-gradient(180deg, ${C.panel} 0%, ${C.bg} 100%)`,
          borderBottom: `1px solid ${C.border}`,
          boxShadow: '0 8px 24px -12px rgba(0,0,0,.5)',
        }}
      >
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <div
            className="h-9 w-9 rounded-xl flex items-center justify-center"
            style={{ background: C.lime, boxShadow: `0 0 20px -4px ${C.lime}88` }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M4 20L14 4L20 14L10 20" stroke={C.onLime} strokeWidth="2.75" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <span className="hidden md:block font-bold text-sm tracking-tight">Hole</span>
        </div>

        <nav
          className="flex items-center gap-1 p-1 rounded-full flex-wrap"
          style={{ background: C.panelAlt, border: `1px solid ${C.border}` }}
        >
          {NAV_ITEMS.map((item) => (
            <NavPill
              key={item.href}
              href={item.href}
              label={item.label}
              icon={item.icon}
              active={isActive(item.href)}
              badge={item.badgeKey ? nav[item.badgeKey] : undefined}
            />
          ))}
        </nav>

        <div className="flex items-center gap-2.5 ml-auto">
          <div className="hidden lg:flex items-center gap-2 rounded-full px-3 h-9 w-44" style={{ background: C.panelAlt, border: `1px solid ${C.border}` }}>
            <Search size={14} style={{ color: C.textMute }} />
            <input
              type="text"
              placeholder="Search"
              className="focus-ring bg-transparent outline-none text-xs flex-1 min-w-0"
              style={{ color: C.text }}
            />
            <span className="px-1 rounded flex-shrink-0" style={{ color: C.textMute, border: `1px solid ${C.border}`, fontSize: '10px' }}>
              &#8984;K
            </span>
          </div>

          <Dropdown label="Year to Date" options={['This Month', 'Last Month', 'Last 3 Months', 'Last 12 Months', 'Year to Date']} />

          <button
            type="button"
            onClick={() => showToast('Download started')}
            className="btn-primary focus-ring hidden md:flex items-center gap-2 px-3 h-9 rounded-full text-xs font-semibold"
            style={{ background: C.lime, color: C.onLime, boxShadow: `0 4px 16px -4px ${C.lime}66` }}
          >
            <Download size={14} /> Download
          </button>

          <button
            type="button"
            onClick={() => showToast('Nothing new')}
            aria-label="Notifications"
            className="icon-btn focus-ring relative h-9 w-9 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ background: C.panelAlt, border: `1px solid ${C.border}` }}
          >
            <Bell size={15} style={{ color: C.textSub }} />
            <span className="absolute top-2 right-2 h-1.5 w-1.5 rounded-full" style={{ background: C.lime }} />
          </button>

          <a href="/profile" className="focus-ring flex-shrink-0 rounded-full" aria-label="Profile">
            <Avatar name={title === 'Profile' ? undefined : 'Ishaan Jain'} size={34} />
          </a>
        </div>
      </header>

      {(title || subtitle) && (
        <div className="px-6 pt-4 flex-shrink-0">
          <div className="text-lg font-bold tracking-tight">{title}</div>
          {subtitle && <div className="text-xs mt-0.5" style={{ color: C.textSub }}>{subtitle}</div>}
        </div>
      )}

      <main className="flex-1 overflow-auto p-6">
        {children}
      </main>

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
