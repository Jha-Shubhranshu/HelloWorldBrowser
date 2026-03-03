// src/components/modals/Createspacemodal.tsx
import { useState, type FormEvent } from 'react'
import type { SpaceCreate } from '../../api/types'

interface Props {
  onClose:  () => void
  onCreate: (data: SpaceCreate) => void
  loading:  boolean
}

export default function CreateSpaceModal({ onClose, onCreate, loading }: Props) {
  const [title, setTitle] = useState('')
  const [desc,  setDesc]  = useState('')

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!title.trim()) return
    onCreate({ title: title.trim(), description: desc.trim() })
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <div style={styles.modalHead}>
          <h2 style={styles.modalTitle}>New Space</h2>
          <button style={styles.closeBtn} onClick={onClose}>✕</button>
        </div>
        <p style={styles.hint}>
          Create a space to organize your video research and prompts.
        </p>
        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>
            Space Title
            <input
              style={styles.input}
              placeholder="e.g. AI Research"
              value={title}
              onChange={e => setTitle(e.target.value)}
              autoFocus
              maxLength={100}
            />
          </label>
          <label style={styles.label}>
            Description (Optional)
            <textarea
              style={{ ...styles.input, ...styles.textarea }}
              placeholder="What is this space for?"
              value={desc}
              onChange={e => setDesc(e.target.value)}
              rows={3}
              maxLength={500}
            />
          </label>
          <div style={styles.actions}>
            <button type="button" style={styles.cancelBtn} onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              style={{ ...styles.submitBtn, ...(loading ? styles.disabled : {}) }}
              disabled={loading || !title.trim()}
            >
              {loading ? 'Creating…' : 'Create Space'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    zIndex: 200,
    backdropFilter: 'blur(4px)',
  },
  modal: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border-hi)',
    borderRadius: 'var(--radius)',
    width: '100%', maxWidth: '440px',
    padding: '28px',
    display: 'flex', flexDirection: 'column', gap: '16px',
  },
  modalHead: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  },
  modalTitle: {
    fontFamily: 'var(--font-head)', fontWeight: 800,
    fontSize: '20px', color: 'var(--text-1)',
  },
  closeBtn: {
    background: 'none', border: 'none',
    color: 'var(--text-3)', cursor: 'pointer', fontSize: '16px',
  },
  hint: {
    fontSize: '14px', color: 'var(--text-3)', lineHeight: 1.5,
  },
  form: {
    display: 'flex', flexDirection: 'column', gap: '20px', marginTop: '8px',
  },
  label: {
    display: 'flex', flexDirection: 'column', gap: '8px',
    fontSize: '13px', fontWeight: 600, color: 'var(--text-2)',
  },
  input: {
    background: 'var(--bg-input)', border: '1.5px solid var(--border)',
    borderRadius: 'var(--radius-sm)', color: 'var(--text-1)',
    padding: '10px 12px', fontSize: '14px', outline: 'none',
    transition: 'border-color var(--transition)',
  },
  textarea: {
    resize: 'vertical', minHeight: '80px', fontFamily: 'inherit',
  },
  actions: {
    display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '10px',
  },
  cancelBtn: {
    background: 'none', border: 'none', color: 'var(--text-3)',
    cursor: 'pointer', fontSize: '14px', fontWeight: 500,
    padding: '8px 12px',
  },
  submitBtn: {
    background: 'var(--accent)', border: 'none', color: 'white',
    borderRadius: 'var(--radius-sm)', padding: '8px 20px',
    fontSize: '14px', fontWeight: 600, cursor: 'pointer',
    transition: 'opacity var(--transition)',
  },
  disabled: {
    opacity: 0.6, cursor: 'not-allowed',
  },
}