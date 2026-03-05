// src/components/SearchBar.tsx
import { useState, type FormEvent } from 'react'
import type { MetadataFilters } from '../api/types'

interface Props {
  onSearch: (query: string, filters: MetadataFilters, topK: number, scopedResults: boolean) => void
  isLoading: boolean
  initialQuery?: string
}

export default function SearchBar({ onSearch, isLoading, initialQuery }: Props) {
  const [query, setQuery]   = useState(initialQuery || '')
  const [topK,  setTopK]    = useState(5)
  const [lang,  setLang]    = useState('')
  const [scoped, setScoped] = useState(false)
  const [showFilters, setShowFilters] = useState(false)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    const filters: MetadataFilters = {}
    if (lang.trim()) filters.transcript_language = lang.trim()
    onSearch(query.trim(), filters, topK, scoped)
  }

  return (
    <form onSubmit={handleSubmit} style={styles.form}>
      {/* Main search row */}
      <div style={styles.inputRow}>
        <div style={styles.inputWrap}>
          <svg style={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            style={styles.input}
            type="text"
            placeholder="Describe the kind of videos you're looking for…"
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
          />
        </div>
        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          style={{ ...styles.btn, ...(isLoading ? styles.btnDisabled : {}) }}
        >
          {isLoading ? <Spinner /> : 'Scout'}
        </button>
      </div>

      {/* Filter toggle */}
      <button
        type="button"
        onClick={() => setShowFilters(v => !v)}
        style={styles.filterToggle}
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
          <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
        </svg>
        {showFilters ? 'Hide filters' : 'Filters'}
      </button>

      {/* Filters panel */}
      {showFilters && (
        <div style={styles.filters}>
          <label style={styles.label}>
            Language
            <input
              style={styles.filterInput}
              type="text"
              placeholder="e.g. English"
              value={lang}
              onChange={e => setLang(e.target.value)}
            />
          </label>
          <label style={styles.label}>
            Results
            <select
              style={styles.filterInput}
              value={topK}
              onChange={e => setTopK(Number(e.target.value))}
            >
              {[3, 5, 10, 20].map(n => (
                <option key={n} value={n}>{n} videos</option>
              ))}
            </select>
          </label>
          <label style={{ ...styles.label, cursor: 'pointer' }}>
            Scoped Results?
            <div 
              onClick={() => setScoped(!scoped)}
              style={{
                ...styles.filterInput,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: scoped ? 'var(--accent)' : 'var(--bg-input)',
                color: scoped ? '#000' : 'var(--text-3)',
                fontWeight: scoped ? 700 : 400,
                transition: 'all 0.2s',
                textAlign: 'center',
                height: '36px',
                padding: '0 12px'
              }}
            >
              {scoped ? 'ENABLED' : 'DISABLED'}
            </div>
          </label>
        </div>
      )}
    </form>
  )
}

function Spinner() {
  return (
    <svg
      width="18" height="18" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2.5"
      style={{ animation: 'spin 0.7s linear infinite' }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
  )
}

const styles: Record<string, React.CSSProperties> = {
  form: {
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  inputRow: {
    display: 'flex',
    gap: '10px',
    alignItems: 'stretch',
  },
  inputWrap: {
    flex: 1,
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  },
  icon: {
    position: 'absolute',
    left: '16px',
    width: '18px',
    height: '18px',
    color: 'var(--text-3)',
    pointerEvents: 'none',
    flexShrink: 0,
  },
  input: {
    width: '100%',
    background: 'var(--bg-input)',
    border: '1.5px solid var(--border)',
    borderRadius: 'var(--radius)',
    color: 'var(--text-1)',
    fontFamily: 'var(--font-body)',
    fontSize: '15px',
    padding: '14px 16px 14px 46px',
    outline: 'none',
    transition: 'border-color var(--transition)',
  },
  btn: {
    background: 'var(--accent)',
    color: '#000',
    border: 'none',
    borderRadius: 'var(--radius)',
    fontFamily: 'var(--font-head)',
    fontWeight: 700,
    fontSize: '15px',
    padding: '0 28px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    whiteSpace: 'nowrap',
    transition: 'opacity var(--transition)',
    minWidth: '100px',
  },
  btnDisabled: {
    opacity: 0.5,
    cursor: 'not-allowed',
  },
  filterToggle: {
    background: 'none',
    border: 'none',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-body)',
    fontSize: '13px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '2px 0',
    alignSelf: 'flex-start',
    transition: 'color var(--transition)',
  },
  filters: {
    display: 'flex',
    gap: '12px',
    flexWrap: 'wrap',
    padding: '14px',
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
  },
  label: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
    fontSize: '12px',
    color: 'var(--text-2)',
    fontFamily: 'var(--font-body)',
    letterSpacing: '0.05em',
    textTransform: 'uppercase',
  },
  filterInput: {
    background: 'var(--bg-input)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-1)',
    fontFamily: 'var(--font-body)',
    fontSize: '14px',
    padding: '8px 10px',
    outline: 'none',
    minWidth: '160px',
  },
}