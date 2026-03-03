import { useState } from 'react'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import HomePage from './components/HomePage'
import SpacePage from './components/SpacePage'
import SearchPage from './pages/Searchpage'
import CreateSpaceModal from './components/modals/Createspacemodal'
import { useSpaces, useCreateSpace } from './api/spacesApi'
import type { SpaceCreate } from './api/types'

type View = { type: 'home' } | { type: 'space'; id: string } | { type: 'search' }

function App() {
  const [view, setView] = useState<View>({ type: 'home' })
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)

  const { data: spaceData } = useSpaces()
  const createSpace = useCreateSpace()

  const spaces = spaceData?.spaces ?? []

  async function handleCreateSpace(data: SpaceCreate) {
    const newSpace = await createSpace.mutateAsync(data)
    setShowCreateModal(false)
    setView({ type: 'space', id: newSpace.id })
  }

  return (
    <div className="app-container" style={styles.container}>
      <Header 
        onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)} 
        onHome={() => setView({ type: 'home' })}
      />
      
      <div style={styles.main}>
        {!sidebarCollapsed && (
          <Sidebar 
            spaces={spaces}
            activeSpaceId={view.type === 'space' ? view.id : null}
            onSelectSpace={(id) => setView({ type: 'space', id })}
            onCreateSpace={() => setShowCreateModal(true)}
            onCollapse={() => setSidebarCollapsed(true)}
          />
        )}

        <main style={styles.content}>
          {view.type === 'home' && (
            <HomePage 
              spaces={spaces}
              onSelectSpace={(id) => setView({ type: 'space', id })}
              onCreateSpace={() => setShowCreateModal(true)}
            />
          )}

          {view.type === 'space' && (
            <SpacePage 
              spaceId={view.id}
              onBack={() => setView({ type: 'home' })}
            />
          )}

          {view.type === 'search' && (
            <SearchPage />
          )}

          {/* Quick toggle for SearchPage (since it's not in sidebar yet) */}
          <button 
            style={styles.searchFab} 
            onClick={() => setView(v => v.type === 'search' ? { type: 'home' } : { type: 'search' })}
            title="Global Search"
          >
            {view.type === 'search' ? '✕' : '🔍'}
          </button>
        </main>
      </div>

      {showCreateModal && (
        <CreateSpaceModal 
          onClose={() => setShowCreateModal(false)}
          onCreate={handleCreateSpace}
          loading={createSpace.isPending}
        />
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    background: 'var(--bg-app)',
    color: 'var(--text-1)',
  },
  main: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },
  content: {
    flex: 1,
    overflowY: 'auto',
    position: 'relative',
  },
  searchFab: {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    width: '48px',
    height: '48px',
    borderRadius: '50%',
    background: 'var(--accent)',
    color: 'white',
    border: 'none',
    cursor: 'pointer',
    boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '20px',
    zIndex: 100,
  }
}

export default App
