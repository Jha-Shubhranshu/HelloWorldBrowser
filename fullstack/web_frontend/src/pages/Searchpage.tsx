import { useEffect } from 'react'
import type { MetadataFilters, SearchResponse, VideoResult } from '../api/types'
import { useSearch } from '../api/searchApi'
import SearchBar from '../components/Searchbar'
import VideoCard from '../components/Videocard'

interface Props {
  initialQuery?: string
}

export default function SearchPage({ initialQuery }: Props) {
  const { mutate, data, isPending, isError, error } = useSearch()

  useEffect(() => {
    if (initialQuery) {
      mutate({ query: initialQuery, filters: {}, top_k: 5, use_llm: false, scoped_results: false })
    }
  }, [initialQuery, mutate])

  function handleSearch(query: string, filters: MetadataFilters, topK: number, scopedResults: boolean) {
    mutate({ query, filters, top_k: topK, use_llm: false, scoped_results: scopedResults })
  }

  return (
    <div style={styles.page}>
      {/* Search */}
      <div style={styles.searchWrap}>
        <SearchBar onSearch={handleSearch} isLoading={isPending} initialQuery={initialQuery} />
      </div>

      {/* States */}
      {isPending && <LoadingState />}

      {isError && (
        <div style={styles.errorBox}>
          <span style={{ color: 'var(--red)', fontWeight: 600 }}>Error — </span>
          {error?.message ?? 'Something went wrong.'}
        </div>
      )}

      {data && !isPending && (
        <Results data={data} />
      )}

      {!data && !isPending && (
        <EmptyState />
      )}
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function Results({ data }: { data: SearchResponse }) {
  if (data.total_matches === 0) {
    return (
      <div style={styles.emptyMsg}>
        No results found for <em>"{data.query}"</em>. Try a broader description.
      </div>
    )
  }

  return (
    <section style={styles.results}>
      <div style={styles.resultsHeader}>
        <span style={styles.resultsCount}>
          {data.total_matches} video{data.total_matches !== 1 ? 's' : ''} matched
        </span>
        <span style={styles.resultsQuery}>"{data.query}"</span>
      </div>

      {data.llm_answer && (
        <div style={styles.llmBox}>
          <span style={styles.llmLabel}>AI Summary</span>
          <p style={styles.llmText}>{data.llm_answer}</p>
        </div>
      )}

      <div style={styles.grid}>
        {data.results.map((r: VideoResult, i: number) => (
          <VideoCard key={r.video_url} result={r} rank={i + 1} />
        ))}
      </div>
    </section>
  )
}

function EmptyState() {
  const suggestions = [
    'channels that explain machine learning simply',
    'cooking tutorials focused on Italian cuisine',
    'finance advice for young professionals',
    'indie game development devlogs',
  ]
  return (
    <div style={styles.emptyState}>
      <p style={styles.emptyTitle}>What are you looking for?</p>
      <div style={styles.suggestions}>
        {suggestions.map(s => (
          <span key={s} style={styles.suggestionChip}>{s}</span>
        ))}
      </div>
    </div>
  )
}

function LoadingState() {
  return (
    <div style={styles.loading}>
      <div style={styles.loadingDots}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            ...styles.dot,
            animationDelay: `${i * 0.15}s`,
          }} />
        ))}
      </div>
      <p style={styles.loadingText}>Searching the vector space…</p>
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.3; }
          40%            { transform: translateY(-8px); opacity: 1; }
        }
      `}</style>
    </div>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh',
    width: '100%',
    boxSizing: 'border-box',
    padding: '48px 24px 80px',
    display: 'flex',
    flexDirection: 'column',
    gap: '32px',
  },
  header: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  logoWrap: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  logoMark: {
    fontSize: '28px',
    color: 'var(--accent)',
    lineHeight: 1,
  },
  logoText: {
    fontFamily: 'var(--font-head)',
    fontWeight: 800,
    fontSize: '26px',
    letterSpacing: '-0.03em',
    color: 'var(--text-1)',
  },
  tagline: {
    fontSize: '14px',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-body)',
    marginLeft: '38px',
  },
  searchWrap: {
    width: '100%',
  },
  errorBox: {
    background: 'rgba(255,71,87,0.08)',
    border: '1px solid rgba(255,71,87,0.25)',
    borderRadius: 'var(--radius)',
    padding: '14px 16px',
    fontSize: '14px',
    color: 'var(--text-2)',
  },
  results: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  resultsHeader: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '12px',
    flexWrap: 'wrap',
  },
  resultsCount: {
    fontFamily: 'var(--font-head)',
    fontWeight: 700,
    fontSize: '15px',
    color: 'var(--accent)',
  },
  resultsQuery: {
    fontSize: '13px',
    color: 'var(--text-3)',
    fontStyle: 'italic',
  },
  llmBox: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border-hi)',
    borderLeft: '3px solid var(--accent)',
    borderRadius: 'var(--radius)',
    padding: '16px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  llmLabel: {
    fontSize: '11px',
    fontFamily: 'var(--font-head)',
    fontWeight: 700,
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
    color: 'var(--accent)',
  },
  llmText: {
    fontSize: '14px',
    color: 'var(--text-2)',
    lineHeight: 1.65,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: '16px',
  },
  emptyMsg: {
    textAlign: 'center',
    color: 'var(--text-3)',
    fontSize: '14px',
    padding: '40px 0',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    paddingTop: '12px',
  },
  emptyTitle: {
    fontSize: '13px',
    color: 'var(--text-3)',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    fontFamily: 'var(--font-head)',
  },
  suggestions: {
    display: 'flex',
    gap: '10px',
    flexWrap: 'wrap',
  },
  suggestionChip: {
    fontSize: '13px',
    padding: '8px 14px',
    borderRadius: '999px',
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    color: 'var(--text-2)',
    cursor: 'default',
    fontFamily: 'var(--font-body)',
  },
  loading: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '14px',
    padding: '48px 0',
  },
  loadingDots: {
    display: 'flex',
    gap: '8px',
  },
  dot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    background: 'var(--accent)',
    display: 'inline-block',
    animation: 'bounce 1.2s ease-in-out infinite',
  },
  loadingText: {
    fontSize: '13px',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-body)',
  },
}