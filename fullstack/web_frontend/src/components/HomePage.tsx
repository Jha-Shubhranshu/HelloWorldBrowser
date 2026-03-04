// src/pages/HomePage.tsx
import type { Space } from '../api/types'

interface Props {
  spaces:        Space[]
  onSelectSpace: (id: string) => void
  onCreateSpace: () => void
}

export default function HomePage({ spaces, onSelectSpace, onCreateSpace }: Props) {
  return (
    <div style={styles.page}>
      {/* Hero */}
      <div style={styles.hero}>
        <h1 style={styles.heroTitle}>Your Spaces</h1>
        <p style={styles.heroSub}>
          Organise semantic video searches into focused research spaces.
        </p>
        <button style={styles.createBtn} onClick={onCreateSpace}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="16" height="16">
            <path d="M12 5v14M5 12h14"/>
          </svg>
          New Space
        </button>
      </div>

      {/* Grid */}
      {spaces.length === 0 ? (
        <div style={styles.empty}>
          <span style={styles.emptyIcon}>◈</span>
          <p style={styles.emptyTitle}>No spaces yet</p>
          <p style={styles.emptySub}>Create your first space to start saving video searches.</p>
        </div>
      ) : (
        <div style={styles.grid}>
          {spaces.map(s => (
            <SpaceCard key={s.id} space={s} onClick={() => onSelectSpace(s.id)} />
          ))}
        </div>
      )}
    </div>
  )
}

function SpaceCard({ space, onClick }: { space: Space; onClick: () => void }) {
  return (
    <button
      style={styles.card}
      onClick={onClick}
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
      <span style={styles.cardIcon}>◈</span>
      <h3 style={styles.cardTitle}>{space.title}</h3>
      {space.description && (
        <p style={styles.cardDesc}>{space.description.slice(0, 100)}{space.description.length > 100 ? '…' : ''}</p>
      )}
      <span style={styles.cardDate}>
        {new Date(space.created_at).toLocaleDateString('en-US', {
          month: 'short', day: 'numeric', year: 'numeric',
        })}
      </span>
    </button>
  )
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    padding: '48px 40px 80px',
    display: 'flex',
    flexDirection: 'column',
    gap: '40px',
    width: '100%',
    boxSizing: 'border-box',
  },
  hero: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  heroTitle: {
    fontFamily: 'var(--font-head)',
    fontWeight: 800,
    fontSize: '32px',
    letterSpacing: '-0.03em',
    color: 'var(--text-1)',
  },
  heroSub: {
    fontSize: '15px',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-body)',
  },
  createBtn: {
    marginTop: '8px',
    alignSelf: 'flex-start',
    background: 'var(--accent)',
    color: '#000',
    border: 'none',
    borderRadius: 'var(--radius-sm)',
    fontFamily: 'var(--font-head)',
    fontWeight: 700,
    fontSize: '14px',
    padding: '10px 20px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
    gap: '16px',
  },
  card: {
    background: 'var(--bg-card)',
    border: '1.5px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '20px',
    cursor: 'pointer',
    textAlign: 'left',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    transition: 'border-color var(--transition), transform var(--transition)',
  },
  cardIcon: {
    fontSize: '20px',
    color: 'var(--accent)',
  },
  cardTitle: {
    fontFamily: 'var(--font-head)',
    fontWeight: 700,
    fontSize: '16px',
    color: 'var(--text-1)',
    letterSpacing: '-0.01em',
  },
  cardDesc: {
    fontSize: '13px',
    color: 'var(--text-2)',
    lineHeight: 1.5,
    fontFamily: 'var(--font-body)',
  },
  cardDate: {
    marginTop: 'auto',
    fontSize: '11px',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-body)',
  },
  empty: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '10px',
    padding: '80px 0',
  },
  emptyIcon: { fontSize: '40px', color: 'var(--text-3)' },
  emptyTitle: {
    fontFamily: 'var(--font-head)',
    fontWeight: 700,
    fontSize: '18px',
    color: 'var(--text-2)',
  },
  emptySub: {
    fontSize: '13px',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-body)',
  },
}