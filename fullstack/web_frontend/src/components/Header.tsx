// src/components/Header.tsx

interface Props {
  onToggleSidebar: () => void
  onHome:          () => void
}

export default function Header({ onToggleSidebar, onHome }: Props) {
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