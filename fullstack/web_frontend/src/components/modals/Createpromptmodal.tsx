// src/components/CreatePromptModal.tsx
import { useState, type FormEvent } from 'react'
import type { PromptCreate } from '../../api/types'

interface Props {
  onClose:  () => void
  onCreate: (data: PromptCreate) => void
  loading:  boolean
}

export default function CreatePromptModal({ onClose, onCreate, loading }: Props) {
  const [query, setQuery]   = useState('')
  const [topK,  setTopK]    = useState(5)
  const [scoped, setScoped] = useState(false)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    onCreate({ 
      query_text: query.trim(), 
      top_k: topK,
      scoped_results: scoped
    })
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={e => e.stopPropagation()}>
        <div style={styles.modalHead}>
          <h2 style={styles.modalTitle}>New Prompt</h2>
          <button style={styles.closeBtn} onClick={onClose}>✕</button>
        </div>
        <p style={styles.hint}>
          Describe the kind of videos you want to find. Results will be saved to this space.
        </p>
        <form onSubmit={handleSubmit} style={styles.form}>
          <label style={styles.label}>
            Query
            <textarea
              style={{ ...styles.input, ...styles.textarea }}
              placeholder="e.g. beginner-friendly tutorials on transformer architectures"
              value={query}
              onChange={e => setQuery(e.target.value)}
              autoFocus
              rows={3}
              maxLength={1000}
            />
          </label>
          <div style={{ display: 'flex', gap: '16px' }}>
            <label style={{ ...styles.label, flex: 1 }}>
              Results to fetch
              <select
                style={styles.input}
                value={topK}
                onChange={e => setTopK(Number(e.target.value))}
              >
                {[3, 5, 10, 20].map(n => (
                  <option key={n} value={n}>{n} videos</option>
                ))}
              </select>
            </label>
            <label style={{ ...styles.label, flex: 1, cursor: 'pointer' }}>
              Scoped Results?
              <div 
                onClick={() => setScoped(!scoped)}
                style={{
                  ...styles.input,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: scoped ? 'var(--accent)' : 'var(--bg-input)',
                  color: scoped ? '#000' : 'var(--text-3)',
                  fontWeight: scoped ? 700 : 400,
                  transition: 'all 0.2s',
                }}
              >
                {scoped ? 'ENABLED' : 'DISABLED'}
              </div>
            </label>
          </div>
          <div style={styles.actions}>
            <button type="button" style={styles.cancelBtn} onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              style={{ ...styles.submitBtn, ...(loading ? styles.disabled : {}) }}
              disabled={loading || !query.trim()}
            >
              {loading ? 'Searching…' : 'Run Prompt'}
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
    width: '100%', maxWidth: '500px',
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
    fontSize: '13px', color: 'var(--text-3)',
    fontFamily: 'var(--font-body)', lineHeight: 1.5,
  },
  form: { display: 'flex', flexDirection: 'column', gap: '14px' },
  label: {
    display: 'flex', flexDirection: 'column', gap: '6px',
    fontSize: '12px', color: 'var(--text-2)',
    fontFamily: 'var(--font-body)',
    letterSpacing: '0.05em', textTransform: 'uppercase',
  },
  input: {
    background: 'var(--bg-input)', border: '1.5px solid var(--border)',
    borderRadius: 'var(--radius-sm)', color: 'var(--text-1)',
    fontFamily: 'var(--font-body)', fontSize: '14px',
    padding: '10px 12px', outline: 'none', width: '100%',
  },
  textarea: { resize: 'vertical', minHeight: '80px' },
  actions: { display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '4px' },
  cancelBtn: {
    background: 'none', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', color: 'var(--text-2)',
    fontFamily: 'var(--font-body)', fontSize: '14px',
    padding: '9px 18px', cursor: 'pointer',
  },
  submitBtn: {
    background: 'var(--accent)', border: 'none',
    borderRadius: 'var(--radius-sm)', color: '#000',
    fontFamily: 'var(--font-head)', fontWeight: 700, fontSize: '14px',
    padding: '9px 20px', cursor: 'pointer',
  },
  disabled: { opacity: 0.5, cursor: 'not-allowed' },
}