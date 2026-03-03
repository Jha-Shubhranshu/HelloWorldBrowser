// src/components/VideoCard.tsx
import type { VideoResult } from '../api/types'

interface Props {
  result: VideoResult
  rank:   number
}

export default function VideoCard({ result, rank }: Props) {
  const score = Math.round(result.score * 100)

  const scoreColor =
    score >= 80 ? '#e8ff47' :
    score >= 60 ? '#66d9a0' :
    score >= 40 ? '#ffa94d' : '#ff6b6b'

  return (
    <a
      href={result.video_url}
      target="_blank"
      rel="noopener noreferrer"
      style={styles.card}
      onMouseEnter={e => {
        const el = e.currentTarget as HTMLElement
        el.style.borderColor = 'var(--border-hi)'
        el.style.transform = 'translateY(-2px)'
      }}
      onMouseLeave={e => {
        const el = e.currentTarget as HTMLElement
        el.style.borderColor = 'var(--border)'
        el.style.transform = 'translateY(0)'
      }}
    >
      {/* Thumbnail */}
      <div style={styles.thumbWrap}>
        {result.video_thumbnail_url ? (
          <img
            src={result.video_thumbnail_url}
            alt={result.video_title}
            style={styles.thumb}
            loading="lazy"
            onError={e => {
              (e.currentTarget as HTMLImageElement).style.display = 'none'
            }}
          />
        ) : (
          <div style={styles.thumbPlaceholder}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" width="28" height="28" style={{ color: 'var(--text-3)' }}>
              <polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/>
            </svg>
          </div>
        )}
        {/* Score badge */}
        <div style={{ ...styles.scoreBadge, color: scoreColor, borderColor: scoreColor }}>
          {score}%
        </div>
        {/* Duration badge */}
        {result.video_length && (
          <div style={styles.durationBadge}>{result.video_length}</div>
        )}
      </div>

      {/* Content */}
      <div style={styles.content}>
        {/* Rank + channel */}
        <div style={styles.meta}>
          <span style={styles.rank}>#{rank}</span>
          <span style={styles.channel}>{result.channel_name}</span>
          {result.video_upload_date && (
            <span style={styles.date}>
              {formatDate(result.video_upload_date)}
            </span>
          )}
        </div>

        {/* Title */}
        <h3 style={styles.title}>{result.video_title || 'Untitled'}</h3>

        {/* Snippet */}
        {result.snippet && (
          <p style={styles.snippet}>"{truncate(result.snippet, 160)}"</p>
        )}

        {/* Footer tags */}
        <div style={styles.tags}>
          {result.transcript_language && (
            <Tag label={result.transcript_language} />
          )}
          {result.video_length && (
            <Tag label={result.video_length} />
          )}
        </div>
      </div>
    </a>
  )
}

function Tag({ label }: { label: string }) {
  return (
    <span style={{
      fontSize: '11px',
      padding: '3px 8px',
      borderRadius: '999px',
      background: 'var(--bg)',
      border: '1px solid var(--border)',
      color: 'var(--text-3)',
      fontFamily: 'var(--font-body)',
      letterSpacing: '0.04em',
    }}>
      {label}
    </span>
  )
}

function truncate(str: string, n: number) {
  return str.length > n ? str.slice(0, n) + '…' : str
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return iso
  }
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    display: 'flex',
    flexDirection: 'column',
    background: 'var(--bg-card)',
    border: '1.5px solid var(--border)',
    borderRadius: 'var(--radius)',
    overflow: 'hidden',
    textDecoration: 'none',
    color: 'inherit',
    transition: 'border-color var(--transition), transform var(--transition)',
    cursor: 'pointer',
  },
  thumbWrap: {
    position: 'relative',
    width: '100%',
    aspectRatio: '16/9',
    background: 'var(--bg)',
    overflow: 'hidden',
  },
  thumb: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    display: 'block',
  },
  thumbPlaceholder: {
    width: '100%',
    height: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--bg-input)',
  },
  scoreBadge: {
    position: 'absolute',
    top: '8px',
    right: '8px',
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-head)',
    padding: '3px 8px',
    borderRadius: '999px',
    background: 'rgba(0,0,0,0.75)',
    border: '1px solid',
    backdropFilter: 'blur(4px)',
  },
  durationBadge: {
    position: 'absolute',
    bottom: '8px',
    right: '8px',
    fontSize: '11px',
    fontWeight: 600,
    fontFamily: 'var(--font-body)',
    padding: '2px 6px',
    borderRadius: '4px',
    background: 'rgba(0,0,0,0.8)',
    color: '#fff',
  },
  content: {
    padding: '14px 16px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    flex: 1,
  },
  meta: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    flexWrap: 'wrap',
  },
  rank: {
    fontSize: '11px',
    fontWeight: 700,
    fontFamily: 'var(--font-head)',
    color: 'var(--accent)',
    letterSpacing: '0.05em',
  },
  channel: {
    fontSize: '12px',
    color: 'var(--text-2)',
    fontWeight: 500,
  },
  date: {
    fontSize: '11px',
    color: 'var(--text-3)',
    marginLeft: 'auto',
  },
  title: {
    fontSize: '14px',
    fontWeight: 600,
    fontFamily: 'var(--font-head)',
    color: 'var(--text-1)',
    lineHeight: 1.4,
    letterSpacing: '-0.01em',
  },
  snippet: {
    fontSize: '13px',
    color: 'var(--text-2)',
    lineHeight: 1.55,
    fontStyle: 'italic',
  },
  tags: {
    display: 'flex',
    gap: '6px',
    flexWrap: 'wrap',
    marginTop: '4px',
  },
}