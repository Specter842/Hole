import React from 'react'
import { C } from './tokens.js'
import { Empty } from './components.jsx'

// Ported from the reference dashboard's `regions` ranked list -- a rank
// number, a label, a proportional bar, and the raw value.
export default function RankedList({ rows }) {
  if (!rows || !rows.length) return <Empty />
  const max = Math.max(...rows.map((r) => r[1]), 1)
  return (
    <ol className="flex flex-col">
      {rows.map((row, i) => (
        <li
          key={row[0] + i}
          className="grid items-center gap-3 py-2.5"
          style={{
            gridTemplateColumns: '22px 1fr 90px 48px',
            borderTop: i === 0 ? 'none' : `1px solid ${C.border}`,
          }}
        >
          <span className="text-xs font-mono" style={{ color: C.textMute }}>
            {i + 1}
          </span>
          <span className="text-sm truncate" style={{ color: C.textSub }} title={row[0]}>
            {row[0]}
          </span>
          <span className="h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,.08)' }}>
            <span
              className="block h-full rounded-full"
              style={{ width: `${(row[1] / max) * 100}%`, background: C.teal }}
            />
          </span>
          <span className="text-xs font-mono text-right tabular-nums" style={{ color: C.text }}>
            {Math.round(row[1]).toLocaleString()}
          </span>
        </li>
      ))}
    </ol>
  )
}
