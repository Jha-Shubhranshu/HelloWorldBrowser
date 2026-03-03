// src/components/PromptRow.tsx
import { useState } from 'react'
import type { Prompt, VideoResult } from '../api/types'

interface Props {
  prompt:   Prompt
  onDelete: (id: string) => void
}

export default function PromptRow({ prompt, onDelete }: Props) {
  const [expanded, setExpanded] = useState(true)
  const results = prompt.results?.results ?? []
  const count   = prompt.results?.total_matches ?? 0

  return (
    <div style={styles.row}>
      {/* Row header */}
      <div style={styles.rowHead}>
        <button style={styles.expandBtn} onClick={() => setExpanded(v => !v)}>
          <svg
            viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
            width="14" height="14"
            style={{ transform: expanded ? 'rotate(90deg)' : 'rotate(0)', transition: 'transform 200ms' }}
          >
            <path d="M9 18l6-6-6-6"/>
          </svg>
        </button>
        <div style={styles.rowMeta}>
          <span style={styles.queryText}>"{prompt.query_text}"</span>
          <span style={styles.countBadge}>{count} video{count !== 1 ? 's' : ''}</span>
          <span style={styles.dateText}>
            {new Date(prompt.created_at).toLocaleDateString('en-US', {
              month: 'short', day: 'numeric', year: 'numeric'
            })}
          </span>
        </div>
        <button
          style={styles.deleteBtn}
          onClick={() => onDelete(prompt.id)}
          title="Delete prompt"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
            <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>
          </svg>
        </button>
      </div>

      {/* Video grid */}
      {expanded && results.length > 0 && (
        <div style={styles.videoGrid}>
          {results.map((v: VideoResult, i: number) => (
            <VideoMiniCard key={v.video_url + i} video={v} rank={i + 1} />
          ))}
        </div>
      )}

      {expanded && results.length === 0 && (
        <p style={styles.noResults}>No results were found for this prompt.</p>
      )}
    </div>
  )
}

function VideoMiniCard({ video, rank }: { video: VideoResult; rank: number }) {
  const score = Math.round(video.score * 100)
  const scoreColor =
    score >= 80 ? '#e8ff47' :
    score >= 60 ? '#66d9a0' :
    score >= 40 ? '#ffa94d' : '#ff6b6b'

  return (
    <a
      href={video.video_url}
      target="_blank"
      rel="noopener noreferrer"
      style={styles.card}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.borderColor = 'var(--border-hi)'
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)'
      }}
    >
      {/* Thumbnail */}
      <div style={styles.thumbWrap}>
        {video.video_thumbnail_url ? (
          <img
            src={video.video_thumbnail_url}
            alt={video.video_title}
            style={styles.thumb}
            loading="lazy"
            onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
          />
        ) : (
          <div style={styles.thumbPlaceholder} />
        )}
        <span style={{ ...styles.scorePill, color: scoreColor, borderColor: scoreColor }}>
          {score}%
        </span>
        {video.video_length && (
          <span style={styles.durationPill}>{video.video_length}</span>
        )}
      </div>

      {/* Info */}
      <div style={styles.cardBody}>
        <p style={styles.cardRank}>#{rank}</p>
        <p style={styles.cardTitle}>{video.video_title || 'Untitled'}</p>
        <p style={styles.cardChannel}>{video.channel_name}</p>
        {video.snippet && (
          <p style={styles.cardSnippet}>"{video.snippet.slice(0, 120)}…"</p>
        )}
      </div>
    </a>
  )
}

const styles: Record<string, React.CSSProperties> = {
  row: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    overflow: 'hidden',
  },
  rowHead: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: '14px 16px',
    borderBottom: '1px solid var(--border)',
  },
  expandBtn: {
    background: 'none', border: 'none',
    color: 'var(--text-3)', cursor: 'pointer',
    display: 'flex', alignItems: 'center',
    padding: '2px', flexShrink: 0,
  },
  rowMeta: {
    flex: 1, display: 'flex', alignItems: 'center',
    gap: '10px', flexWrap: 'wrap',
  },
  queryText: {
    fontFamily: 'var(--font-head)', fontWeight: 600,
    fontSize: '14px', color: 'var(--text-1)',
  },
  countBadge: {
    fontSize: '11px', padding: '2px 8px',
    borderRadius: '999px', background: 'rgba(232,255,71,0.1)',
    color: 'var(--accent)', border: '1px solid rgba(232,255,71,0.2)',
    fontFamily: 'var(--font-body)',
  },
  dateText: {
    fontSize: '11px', color: 'var(--text-3)',
    fontFamily: 'var(--font-body)', marginLeft: 'auto',
  },
  deleteBtn: {
    background: 'none', border: 'none',
    color: 'var(--text-3)', cursor: 'pointer',
    display: 'flex', alignItems: 'center', padding: '4px',
    borderRadius: '4px',
  },
  videoGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
    gap: '12px',
    padding: '16px',
  },
  noResults: {
    fontSize: '13px', color: 'var(--text-3)',
    padding: '16px', fontFamily: 'var(--font-body)',
  },
  card: {
    display: 'flex', flexDirection: 'column',
    background: 'var(--bg)', border: '1.5px solid var(--border)',
    borderRadius: 'var(--radius-sm)', overflow: 'hidden',
    textDecoration: 'none', color: 'inherit',
    transition: 'border-color var(--transition)',
  },
  thumbWrap: {
    position: 'relative', width: '100%', aspectRatio: '16/9',
    background: 'var(--bg-input)', overflow: 'hidden',
  },
  thumb: { width: '100%', height: '100%', objectFit: 'cover', display: 'block' },
  thumbPlaceholder: { width: '100%', height: '100%', background: 'var(--bg-input)' },
  scorePill: {
    position: 'absolute', top: '6px', right: '6px',
    fontSize: '10px', fontWeight: 700, fontFamily: 'var(--font-head)',
    padding: '2px 6px', borderRadius: '999px',
    background: 'rgba(0,0,0,0.75)', border: '1px solid',
  },
  durationPill: {
    position: 'absolute', bottom: '6px', right: '6px',
    fontSize: '10px', fontWeight: 600,
    padding: '2px 5px', borderRadius: '3px',
    background: 'rgba(0,0,0,0.8)', color: '#fff',
  },
  cardBody: {
    padding: '10px 12px',
    display: 'flex', flexDirection: 'column', gap: '4px',
  },
  cardRank: {
    fontSize: '10px', fontWeight: 700, color: 'var(--accent)',
    fontFamily: 'var(--font-head)', letterSpacing: '0.05em',
  },
  cardTitle: {
    fontSize: '13px', fontWeight: 600, color: 'var(--text-1)',
    fontFamily: 'var(--font-head)', lineHeight: 1.35,
  },
  cardChannel: {
    fontSize: '11px', color: 'var(--text-2)',
    fontFamily: 'var(--font-body)',
  },
  cardSnippet: {
    fontSize: '11px', color: 'var(--text-3)',
    fontStyle: 'italic', lineHeight: 1.4, marginTop: '2px',
  },
}