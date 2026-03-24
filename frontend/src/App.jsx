import { useState, useEffect, useRef } from 'react'

const API = '/api'


// Palette (light mode):
//   #0d2347 — dark navy      → sidebar bg, dark text
//   #0d3d7c — royal blue     → sidebar header, active rows
//   #1565c0 — medium blue    → buttons, accents, links
//   #5b8db8 — steel blue     → borders, muted elements
//   #aecde0 — pale blue      → page background, light surfaces
const THEMES = {
  light: {
    // Page & main area
    pageBg:          '#aecde0',   // pale blue — entire page background
    mainBg:          '#ddeef7',   // slightly lighter — answer area
    cardBg:          '#ffffff',   // white — answer box, input bar
    inputBg:         '#ffffff',

    // Sidebar
    sidebarBg:       '#0d2347',   // dark navy
    sidebarBorder:   '#0d3d7c',   // royal blue divider
    sidebarTitle:    '#ffffff',
    sidebarSub:      '#aecde0',   // pale blue subtitle
    sidebarLabel:    '#5b8db8',   // steel blue section labels
    sidebarEmpty:    '#5b8db8',

    // Source rows in sidebar
    sourceRowBg:     '#0d3d7c',   // royal blue row bg
    sourceRowHover:  '#1565c0',   // medium blue on hover
    sourceRowText:   '#ffffff',
    deleteBtn:       '#aecde0',

    // Upload zone
    uploadBorder:    '#5b8db8',
    uploadBorderHover:'#aecde0',
    uploadText:      '#aecde0',
    uploadStrong:    '#ffffff',

    // Refresh button
    refreshColor:    '#aecde0',

    // Button (Ask)
    btnBg:           '#1565c0',   // medium blue
    btnBgDisabled:   '#5b8db8',   // steel blue when disabled
    btnText:         '#ffffff',

    // Input field
    inputBorder:     '#5b8db8',
    inputBorderFocus:'#1565c0',
    inputText:       '#0d2347',
    inputPlaceholder:'#5b8db8',

    // Answer box
    answerBorder:    '#5b8db8',
    answerText:      '#0d2347',

    // Top border between areas
    divider:         '#5b8db8',

    // Placeholder state
    placeholderText: '#5b8db8',

    // Error banner
    errorBg:         '#fee2e2',
    errorBorder:     '#fecaca',
    errorText:       '#991b1b',

    // Theme toggle button
    toggleBg:        '#0d3d7c',
    toggleText:      '#ffffff',
    toggleBorder:    '#1565c0',
  },

  dark: {
    pageBg:          '#060f1a',
    mainBg:          '#0a1628',
    cardBg:          '#0d2040',
    inputBg:         '#0d2040',

    sidebarBg:       '#040d17',
    sidebarBorder:   '#0d2347',
    sidebarTitle:    '#e8f4fd',
    sidebarSub:      '#5b8db8',
    sidebarLabel:    '#5b8db8',
    sidebarEmpty:    '#2a4a6b',

    sourceRowBg:     '#0d2347',
    sourceRowHover:  '#0d3d7c',
    sourceRowText:   '#aecde0',
    deleteBtn:       '#5b8db8',

    uploadBorder:    '#0d3d7c',
    uploadBorderHover:'#1565c0',
    uploadText:      '#5b8db8',
    uploadStrong:    '#aecde0',

    refreshColor:    '#5b8db8',

    btnBg:           '#1565c0',
    btnBgDisabled:   '#0d3d7c',
    btnText:         '#ffffff',

    inputBorder:     '#0d3d7c',
    inputBorderFocus:'#1565c0',
    inputText:       '#e8f4fd',
    inputPlaceholder:'#2a4a6b',

    answerBorder:    '#0d3d7c',
    answerText:      '#e8f4fd',

    divider:         '#0d2347',

    placeholderText: '#2a4a6b',

    errorBg:         '#2d0f0f',
    errorBorder:     '#7f1d1d',
    errorText:       '#fca5a5',

    toggleBg:        '#0d3d7c',
    toggleText:      '#aecde0',
    toggleBorder:    '#1565c0',
  },
}

export default function App() {
  //  — THEME STATE
  // Added `theme` state. Reads from localStorage so the preference persists
  // across page refreshes. Defaults to 'light'.
 const [theme, setTheme] = useState(
    () => localStorage.getItem('rag-theme') || 'light'
  )
  const t = THEMES[theme]   // shorthand — use t.btnBg etc. throughout

  const [sources, setSources]     = useState([])
  const [question, setQuestion]   = useState('')
  const [answer, setAnswer]       = useState('')
  const [streaming, setStreaming] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError]         = useState('')
  const answerRef = useRef(null)

  useEffect(() => { loadSources() }, [])

  useEffect(() => {
    if (answerRef.current)
      answerRef.current.scrollTop = answerRef.current.scrollHeight
  }, [answer])

 //  PERSIST THEME TO LOCALSTORAGE
  // Every time theme changes, save it and update the <html> background so
  // there's no white flash before React renders.
  useEffect(() => {
    localStorage.setItem('rag-theme', theme)
    document.documentElement.style.background = THEMES[theme].pageBg
  }, [theme])

  function toggleTheme() {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  // ── API helpers (unchanged logic, colour-independent) ────────────────────

  async function loadSources() {
    try {
      const res  = await fetch(`${API}/sources`)
      const data = await res.json()
      setSources(data.sources || [])
    } catch (err) {
      console.error('Failed to load sources:', err)
    }
  }

  async function uploadFile(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    setError('')
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch(`${API}/ingest`, { method: 'POST', body: form })
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail) }
      const data = await res.json()
      alert(`✓ Ingested "${data.source}" — ${data.chunks} chunks`)
      loadSources()
    } catch (err) { setError(err.message) }
    setUploading(false)
    e.target.value = ''
  }

  async function askQuestion() {
    if (!question.trim() || streaming) return
    setStreaming(true); setAnswer(''); setError('')
    try {
      const res = await fetch(`${API}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail) }
      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        for (const line of decoder.decode(value).split('\n\n')) {
          if (!line.startsWith('data: ')) continue
          const token = line.slice(6)
          if (token === '[DONE]') break
          setAnswer(prev => prev + token.replace(/<br>/g, '\n'))
        }
      }
    } catch (err) { setError(err.message) }
    setStreaming(false)
  }

  async function deleteSource(name) {
    if (!confirm(`Remove "${name}"?`)) return
    try {
      await fetch(`${API}/sources/${encodeURIComponent(name)}`, { method: 'DELETE' })
      loadSources()
    } catch (err) { setError(err.message) }
  }

  //  Render 

  return (
    // ALL HARDCODED COLOURS REPLACED WITH t.* THEME VALUES
    // Every style property that was a hex string is now a reference to the
    // active theme object. Toggling theme re-renders with the new palette.
    <div style={{ display:'flex', height:'100vh', overflow:'hidden', background: t.pageBg, transition:'background .25s' }}>

      {/*  Sidebar  */}
      <aside style={{
        width: 268, minWidth: 268,
        borderRight: `1px solid ${t.sidebarBorder}`,
        padding: 20,
        display: 'flex', flexDirection: 'column', gap: 20,
        background: t.sidebarBg,
        overflow: 'hidden',
        transition: 'background .25s',
      }}>

        {/* Brand + theme toggle */}
        <div style={{ paddingBottom: 16, borderBottom: `1px solid ${t.sidebarBorder}` }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
            <div>
              <h1 style={{ fontSize:17, fontWeight:700, color: t.sidebarTitle, margin:'0 0 2px' }}>
                RAG Doc Reader
              </h1>
              <p style={{ fontSize:12, color: t.sidebarSub, margin:0 }}>
                Ollama + ChromaDB
              </p>
            </div>

            {/*THEME TOGGLE BUTTON
                New button in the sidebar header. Switches between light/dark
                and shows a sun/moon icon matching the current mode.
            */}
            <button
              onClick={toggleTheme}
              title={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
              style={{
                padding: '5px 10px',
                borderRadius: 8,
                border: `1px solid ${t.toggleBorder}`,
                background: t.toggleBg,
                color: t.toggleText,
                fontSize: 14,
                cursor: 'pointer',
                transition: 'all .2s',
                flexShrink: 0,
              }}
            >
              {theme === 'light' ? '🌙' : '☀️'}
            </button>
          </div>
        </div>

        {/* Upload */}
        <div>
          <p style={{ fontSize:10, fontWeight:700, color: t.sidebarLabel, letterSpacing:0.8, margin:'0 0 8px' }}>
            UPLOAD DOCUMENT
          </p>
          <label
            style={{
              display: 'block',
              padding: '20px 12px',
              border: `2px dashed ${t.uploadBorder}`,
              borderRadius: 8,
              textAlign: 'center',
              cursor: uploading ? 'default' : 'pointer',
              fontSize: 12,
              color: t.uploadText,
              lineHeight: 1.7,
              transition: 'border-color .15s',
            }}
            onMouseEnter={e => { if (!uploading) e.currentTarget.style.borderColor = t.uploadBorderHover }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = t.uploadBorder }}
          >
            {uploading ? 'Indexing...' : (
              <>Click to upload<br />
                <strong style={{ color: t.uploadStrong }}>PDF · TXT · MD · DOCX</strong>
              </>
            )}
            <input type="file" accept=".pdf,.txt,.md,.markdown,.docx"
              onChange={uploadFile} disabled={uploading} style={{ display:'none' }} />
          </label>
        </div>

        {/* Source list */}
        <div style={{ flex:1, overflow:'hidden', display:'flex', flexDirection:'column' }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:8 }}>
            <p style={{ fontSize:10, fontWeight:700, color: t.sidebarLabel, letterSpacing:0.8, margin:0 }}>
              LOADED DOCS
            </p>
            <button onClick={loadSources} style={{
              fontSize:11, color: t.refreshColor,
              background:'none', border:'none', cursor:'pointer', padding:0,
            }}>
              refresh
            </button>
          </div>

          <div style={{ flex:1, overflowY:'auto', display:'flex', flexDirection:'column', gap:4 }}>
            {sources.length === 0
              ? <p style={{ fontSize:12, color: t.sidebarEmpty, textAlign:'center', padding:'14px 0', margin:0 }}>
                  No documents loaded yet
                </p>
              : sources.map(src => (
                  <div
                    key={src}
                    style={{
                      display:'flex', alignItems:'center', gap:6,
                      padding:'7px 10px',
                      background: t.sourceRowBg,
                      borderRadius:6, fontSize:12, color: t.sourceRowText,
                      transition: 'background .15s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = t.sourceRowHover}
                    onMouseLeave={e => e.currentTarget.style.background = t.sourceRowBg}
                  >
                    <span style={{ flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                      {src}
                    </span>
                    <button onClick={() => deleteSource(src)}
                      style={{ color: t.deleteBtn, background:'none', border:'none', cursor:'pointer', fontSize:18, lineHeight:1, padding:0 }}>
                      ×
                    </button>
                  </div>
                ))
            }
          </div>
        </div>

      </aside>

      {/*  Main area  */}
      <main style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden', background: t.mainBg, transition:'background .25s' }}>

        {/* Error banner */}
        {error && (
          <div style={{
            display:'flex', alignItems:'center', justifyContent:'space-between',
            padding:'10px 20px',
            background: t.errorBg,
            borderBottom: `1px solid ${t.errorBorder}`,
            fontSize:13, color: t.errorText,
          }}>
            <strong>Error:</strong>&nbsp;{error}
            <button onClick={() => setError('')}
              style={{ background:'none', border:'none', cursor:'pointer', fontSize:18, color: t.errorText }}>
              ×
            </button>
          </div>
        )}

        {/* Answer area */}
        <div ref={answerRef} style={{ flex:1, padding:'28px 32px', overflowY:'auto' }}>
          {answer ? (
            <div style={{
              maxWidth: 720,
              background: t.cardBg,
              border: `1px solid ${t.answerBorder}`,
              borderRadius: 12,
              padding: '20px 24px',
              fontSize: 14,
              lineHeight: 1.85,
              whiteSpace: 'pre-wrap',
              color: t.answerText,
              transition: 'background .25s, color .25s',
            }}>
              {answer}
              {streaming && <span style={{ opacity:0.4 }}>▌</span>}
            </div>
          ) : (
            <div style={{
              height:'100%', display:'flex', flexDirection:'column',
              alignItems:'center', justifyContent:'center',
              gap:10, color: t.placeholderText, fontSize:14, textAlign:'center',
            }}>
              <div style={{ fontSize:40, marginBottom:4 }}>📄</div>
              <p>Upload a document, then ask anything about it</p>
              <p style={{ fontSize:12, opacity:0.7 }}>Answers are grounded in your document — no hallucination</p>
            </div>
          )}
        </div>

        {/* Input bar */}
        <div style={{
          borderTop: `1px solid ${t.divider}`,
          padding: '14px 20px',
          display: 'flex', gap:10,
          background: t.cardBg,
          alignItems: 'center',
          transition: 'background .25s',
        }}>
          <input
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && askQuestion()}
            placeholder="Ask a question about your documents..."
            disabled={streaming}
            style={{
              flex:1, padding:'11px 14px',
              border: `1px solid ${t.inputBorder}`,
              borderRadius:8, fontSize:14, outline:'none',
              background: t.inputBg,
              color: t.inputText,
              transition: 'border-color .15s, background .25s',
            }}
            onFocus={e => e.target.style.borderColor = t.inputBorderFocus}
            onBlur={e  => e.target.style.borderColor = t.inputBorder}
          />
          <button
            onClick={askQuestion}
            disabled={streaming || !question.trim()}
            style={{
              padding: '11px 24px',
              background: streaming || !question.trim() ? t.btnBgDisabled : t.btnBg,
              color: t.btnText,
              border: 'none', borderRadius:8,
              fontSize:14, fontWeight:500,
              cursor: streaming || !question.trim() ? 'default' : 'pointer',
              transition: 'background .15s',
              whiteSpace: 'nowrap',
            }}
          >
            {streaming ? 'Thinking...' : 'Ask'}
          </button>
        </div>

      </main>
    </div>
  )
}