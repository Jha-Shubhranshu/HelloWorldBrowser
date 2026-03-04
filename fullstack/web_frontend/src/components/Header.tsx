// src/components/Header.tsx

import { useState } from 'react'

interface Props {
  onToggleSidebar: () => void
  onHome:          () => void
  onGlobalSearch:  (query: string) => void
}

export default function Header({ onToggleSidebar, onHome, onGlobalSearch }: Props) {
  const [query, setQuery] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (query.trim()) {
      onGlobalSearch(query.trim())
    }
  }

  return (
    <header style={styles.header}>
      <div style={styles.left}>
        <button style={styles.menuBtn} onClick={onToggleSidebar} title="Toggle sidebar">
          <span style={styles.stackLine} />
          <span style={styles.stackLine} />
          <span style={styles.stackLine} />
        </button>
        <button style={styles.logo} onClick={onHome}>
          <span style={styles.logoMark}>◈</span>
          <span style={styles.logoText}>Channel Scout</span>
        </button>
      </div>

      <div style={styles.center}>
        <form onSubmit={handleSubmit} style={styles.searchForm}>
          <input
            style={styles.searchInput}
            placeholder="Search channels..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" style={styles.searchBtn}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="16" height="16">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
          </button>
        </form>
      </div>

      <div style={styles.right} />
    </header>
  )
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    height: '56px',
    background: 'var(--bg-card)',
    borderBottom: '1px solid var(--border)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 20px',
    position: 'sticky',
    top: 0,
    zIndex: 100,
    flexShrink: 0,
  },
  left: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    minWidth: '240px',
  },
  center: {
    flex: 1,
    display: 'flex',
    justifyContent: 'center',
    maxWidth: '600px',
  },
  right: {
    minWidth: '240px',
  },
  searchForm: {
    display: 'flex',
    width: '100%',
    maxWidth: '560px',
    background: 'var(--bg-app)',
    border: '1px solid var(--border)',
    borderRadius: '20px',
    overflow: 'hidden',
    height: '36px',
  },
  searchInput: {
    flex: 1,
    background: 'none',
    border: 'none',
    padding: '0 16px',
    color: 'var(--text-1)',
    fontSize: '14px',
    outline: 'none',
  },
  searchBtn: {
    background: 'var(--bg-card)',
    border: 'none',
    borderLeft: '1px solid var(--border)',
    padding: '0 16px',
    cursor: 'pointer',
    color: 'var(--text-2)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'background 200ms',
  },
  menuBtn: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '6px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    borderRadius: '4px',
  },
  stackLine: {
    display: 'block',
    width: '18px',
    height: '2px',
    background: 'var(--text-2)',
    borderRadius: '2px',
  },
  logo: {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '4px 0',
  },
  logoMark: {
    fontSize: '20px',
    color: 'var(--accent)',
  },
  logoText: {
    fontFamily: 'var(--font-head)',
    fontWeight: 800,
    fontSize: '18px',
    letterSpacing: '-0.03em',
    color: 'var(--text-1)',
  },
}