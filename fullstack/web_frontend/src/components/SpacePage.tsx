// src/pages/SpacePage.tsx
import { useState } from 'react'
import { useSpace, useUpdateSpace, useDeleteSpace } from '../api/spacesApi'
import { usePrompts, useCreatePrompt, useDeletePrompt } from '../api/promptsApi'
import CreatePromptModal from '../components/modals/Createpromptmodal'
import PromptRow from '../components/Promptrow'
import type { Prompt, PromptCreate } from '../api/types'

interface Props {
  spaceId: string
  onBack:  () => void
}

export default function SpacePage({ spaceId, onBack }: Props) {
  const { data: space, isLoading: spaceLoading } = useSpace(spaceId)
  const { data: promptData, isLoading: promptsLoading } = usePrompts(spaceId)

  const updateSpace  = useUpdateSpace(spaceId)
  const deleteSpace  = useDeleteSpace()
  const createPrompt = useCreatePrompt(spaceId)
  const deletePrompt = useDeletePrompt(spaceId)

  const [showPromptModal, setShowPromptModal] = useState(false)
  const [editingTitle,    setEditingTitle]    = useState(false)
  const [editingDesc,     setEditingDesc]     = useState(false)
  const [titleDraft,      setTitleDraft]      = useState('')
  const [descDraft,       setDescDraft]       = useState('')

  if (spaceLoading) return <div style={styles.loading}>Loading space…</div>
  if (!space)       return <div style={styles.loading}>Space not found.</div>

  function startEditTitle() {
    setTitleDraft(space!.title)
    setEditingTitle(true)
  }
  function saveTitle() {
    if (titleDraft.trim()) updateSpace.mutate({ title: titleDraft.trim() })
    setEditingTitle(false)
  }
  function startEditDesc() {
    setDescDraft(space!.description)
    setEditingDesc(true)
  }
  function saveDesc() {
    updateSpace.mutate({ description: descDraft.trim() })
    setEditingDesc(false)
  }

  async function handleDeleteSpace() {
    if (!confirm(`Delete "${space!.title}"? This cannot be undone.`)) return
    await deleteSpace.mutateAsync(spaceId)
    onBack()
  }

  async function handleCreatePrompt(data: PromptCreate) {
    await createPrompt.mutateAsync(data)
    setShowPromptModal(false)
  }

  const prompts = promptData?.prompts ?? []

  return (
    <div style={styles.page}>
      {/* Breadcrumb */}
      <button style={styles.back} onClick={onBack}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
          <path d="M19 12H5M12 5l-7 7 7 7"/>
        </svg>
        All Spaces
      </button>

      {/* Space header */}
      <div style={styles.spaceHeader}>
        <div style={styles.spaceHeaderLeft}>
          {/* Title */}
          {editingTitle ? (
            <div style={styles.editRow}>
              <input
                style={styles.titleInput}
                value={titleDraft}
                onChange={e => setTitleDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') saveTitle(); if (e.key === 'Escape') setEditingTitle(false) }}
                autoFocus
              />
              <button style={styles.saveBtn} onClick={saveTitle}>Save</button>
              <button style={styles.cancelEditBtn} onClick={() => setEditingTitle(false)}>Cancel</button>
            </div>
          ) : (
            <div style={styles.editRow}>
              <h1 style={styles.spaceTitle}>{space.title}</h1>
              <button style={styles.editIcon} onClick={startEditTitle} title="Edit title">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </button>
            </div>
          )}

          {/* Description */}
          {editingDesc ? (
            <div style={styles.editDescRow}>
              <textarea
                style={styles.descInput}
                value={descDraft}
                onChange={e => setDescDraft(e.target.value)}
                onKeyDown={e => { if (e.key === 'Escape') setEditingDesc(false) }}
                rows={2}
                autoFocus
              />
              <div style={styles.editDescActions}>
                <button style={styles.saveBtn} onClick={saveDesc}>Save</button>
                <button style={styles.cancelEditBtn} onClick={() => setEditingDesc(false)}>Cancel</button>
              </div>
            </div>
          ) : (
            <div style={styles.editRow}>
              <p style={styles.spaceDesc} onClick={startEditDesc}>
                {space.description || <span style={{ color: 'var(--text-3)', fontStyle: 'italic' }}>Add a description…</span>}
              </p>
              <button style={styles.editIcon} onClick={startEditDesc} title="Edit description">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* Actions */}
        <div style={styles.spaceActions}>
          <button style={styles.newPromptBtn} onClick={() => setShowPromptModal(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" width="14" height="14">
              <path d="M12 5v14M5 12h14"/>
            </svg>
            New Prompt
          </button>
          <button style={styles.deleteSpaceBtn} onClick={handleDeleteSpace} title="Delete space">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15">
              <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Prompts */}
      <div style={styles.promptsSection}>
        <div style={styles.sectionHead}>
          <span style={styles.sectionLabel}>Prompts</span>
          <span style={styles.sectionCount}>{prompts.length}</span>
        </div>

        {promptsLoading && <p style={styles.hint}>Loading prompts…</p>}

        {!promptsLoading && prompts.length === 0 && (
          <div style={styles.emptyPrompts}>
            <p style={styles.emptyTitle}>No prompts yet</p>
            <p style={styles.emptyHint}>Run your first prompt to start collecting videos.</p>
            <button style={styles.newPromptBtn} onClick={() => setShowPromptModal(true)}>
              + New Prompt
            </button>
          </div>
        )}

        {prompts.map((p: Prompt) => (
          <PromptRow
            key={p.id}
            prompt={p}
            onDelete={(id) => deletePrompt.mutate(id)}
          />
        ))}
      </div>

      {/* Create Prompt Modal */}
      {showPromptModal && (
        <CreatePromptModal
          onClose={() => setShowPromptModal(false)}
          onCreate={handleCreatePrompt}
          loading={createPrompt.isPending}
        />
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    padding: '32px 40px 80px',
    maxWidth: '1000px',
    margin: '0 auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '32px',
  },
  loading: {
    padding: '60px 40px',
    color: 'var(--text-3)',
    fontFamily: 'var(--font-body)',
    fontSize: '14px',
  },
  back: {
    background: 'none', border: 'none',
    color: 'var(--text-3)', cursor: 'pointer',
    display: 'flex', alignItems: 'center', gap: '6px',
    fontSize: '13px', fontFamily: 'var(--font-body)',
    padding: '0', alignSelf: 'flex-start',
    transition: 'color var(--transition)',
  },
  spaceHeader: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: '20px',
    flexWrap: 'wrap',
  },
  spaceHeaderLeft: {
    display: 'flex', flexDirection: 'column', gap: '8px', flex: 1,
  },
  spaceTitle: {
    fontFamily: 'var(--font-head)', fontWeight: 800,
    fontSize: '28px', letterSpacing: '-0.03em', color: 'var(--text-1)',
  },
  spaceDesc: {
    fontSize: '14px', color: 'var(--text-2)',
    fontFamily: 'var(--font-body)', lineHeight: 1.55,
    cursor: 'text',
  },
  editRow: { display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' },
  editDescRow: { display: 'flex', flexDirection: 'column', gap: '8px' },
  editDescActions: { display: 'flex', gap: '8px' },
  titleInput: {
    background: 'var(--bg-input)', border: '1.5px solid var(--border-hi)',
    borderRadius: 'var(--radius-sm)', color: 'var(--text-1)',
    fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: '24px',
    padding: '6px 10px', outline: 'none',
  },
  descInput: {
    background: 'var(--bg-input)', border: '1.5px solid var(--border-hi)',
    borderRadius: 'var(--radius-sm)', color: 'var(--text-1)',
    fontFamily: 'var(--font-body)', fontSize: '14px',
    padding: '8px 10px', outline: 'none', resize: 'vertical', width: '100%',
  },
  editIcon: {
    background: 'none', border: 'none',
    color: 'var(--text-3)', cursor: 'pointer',
    display: 'flex', alignItems: 'center', padding: '4px',
  },
  saveBtn: {
    background: 'var(--accent)', border: 'none',
    borderRadius: 'var(--radius-sm)', color: '#000',
    fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: '13px',
    padding: '6px 14px', cursor: 'pointer',
  },
  cancelEditBtn: {
    background: 'none', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', color: 'var(--text-2)',
    fontFamily: 'var(--font-body)', fontSize: '13px',
    padding: '6px 14px', cursor: 'pointer',
  },
  spaceActions: { display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 },
  newPromptBtn: {
    background: 'var(--accent)', border: 'none',
    borderRadius: 'var(--radius-sm)', color: '#000',
    fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: '13px',
    padding: '10px 18px', cursor: 'pointer',
    display: 'flex', alignItems: 'center', gap: '6px',
  },
  deleteSpaceBtn: {
    background: 'none', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', color: 'var(--text-3)',
    padding: '9px 10px', cursor: 'pointer',
    display: 'flex', alignItems: 'center',
  },
  promptsSection: { display: 'flex', flexDirection: 'column', gap: '12px' },
  sectionHead: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' },
  sectionLabel: {
    fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: '13px',
    letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-3)',
  },
  sectionCount: {
    fontSize: '12px', padding: '2px 8px', borderRadius: '999px',
    background: 'var(--bg-card)', border: '1px solid var(--border)',
    color: 'var(--text-3)',
  },
  hint: { fontSize: '13px', color: 'var(--text-3)', fontFamily: 'var(--font-body)' },
  emptyPrompts: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    gap: '8px', padding: '48px 0',
    border: '1px dashed var(--border)', borderRadius: 'var(--radius)',
  },
  emptyTitle: {
    fontFamily: 'var(--font-head)', fontWeight: 700,
    fontSize: '16px', color: 'var(--text-2)',
  },
  emptyHint: { fontSize: '13px', color: 'var(--text-3)', fontFamily: 'var(--font-body)' },
}