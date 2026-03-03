// src/components/Sidebar.tsx
import type { Space } from '../api/types'

interface Props {
  spaces:          Space[]
  activeSpaceId:   string | null
  onSelectSpace:   (id: string) => void
  onCreateSpace:   () => void
  onCollapse:      () => void
}

export default function Sidebar({
  spaces, activeSpaceId, onSelectSpace, onCreateSpace, onCollapse,
}: Props) {
  return (
    <aside style={styles.sidebar}>
      {/* Header */}
      <div style={styles.sidebarHead}>
        <span style={styles.sidebarTitle}>Spaces</span>
        <button style={styles.iconBtn} onClick={onCollapse} title="Collapse">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
            <path d="M11 19l-7-7 7-7"/><path d="M19 19l-7-7 7-7"/>
          </svg>
        </button>
      </div>

      {/* New space button */}
      <button style={styles.newSpaceBtn} onClick={onCreateSpace}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        New Space
      </button>

      {/* Space list */}
      <nav style={styles.spaceList}>
        {spaces.length === 0 && (
          <p style={styles.emptyNote}>No spaces yet</p>
        )}
        {spaces.map(s => (
          <button
            key={s.id}
            style={{
              ...styles.spaceItem,
              ...(s.id === activeSpaceId ? styles.spaceItemActive : {}),
            }}
            onClick={() => onSelectSpace(s.id)}
          >
            <span style={styles.spaceIcon}>◈</span>
            <span style={styles.spaceItemTitle}>{s.title}</span>
          </button>
        ))}
      </nav>
    </aside>
  )
}

const styles: Record<string, React.CSSProperties> = {
  sidebar: {
    width: '240px',
    flexShrink: 0,
    background: 'var(--bg-card)',
    borderRight: '1px solid var(--border)',
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    position: 'sticky',
    top: 0,
    overflow: 'hidden',
  },
  sidebarHead: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '20px 16px 12px',
    borderBottom: '1px solid var(--border)',
  },
  sidebarTitle: {
    fontFamily: 'var(--font-head)',
    fontWeight: 700,
    fontSize: '13px',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    color: 'var(--text-3)',
  },
  iconBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-3)',
    cursor: 'pointer',
    padding: '4px',
    display: 'flex',
    alignItems: 'center',
    borderRadius: '4px',
    transition: 'color var(--transition)',
  },
  newSpaceBtn: {
    margin: '12px',
    padding: '9px 12px',
    background: 'var(--accent)',
    color: '#000',
    border: 'none',
    borderRadius: 'var(--radius-sm)',
    fontFamily: 'var(--font-head)',
    fontWeight: 700,
    fontSize: '13px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '7px',
  },
  spaceList: {
    flex: 1,
    overflowY: 'auto',
    padding: '8px 8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
  },
  emptyNote: {
    fontSize: '12px',
    color: 'var(--text-3)',
    padding: '8px 8px',
    fontFamily: 'var(--font-body)',
  },
  spaceItem: {
    width: '100%',
    background: 'none',
    border: 'none',
    borderRadius: 'var(--radius-sm)',
    padding: '9px 10px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    textAlign: 'left',
    transition: 'background var(--transition)',
    color: 'var(--text-2)',
  },
  spaceItemActive: {
    background: 'rgba(232,255,71,0.08)',
    color: 'var(--accent)',
  },
  spaceIcon: {
    fontSize: '12px',
    flexShrink: 0,
  },
  spaceItemTitle: {
    fontSize: '13px',
    fontFamily: 'var(--font-body)',
    fontWeight: 500,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
}