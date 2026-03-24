import { useState, useEffect, useRef} from 'react'

// All API calls go through /api which is a Vite proxy to http://localhost:8000

const API = '/api'

export default function App() {
  const [sources, setSources]     = useState([])
  const [question, setQuestion]   = useState('')
  const [answer, setAnswer]       = useState('')
  const [streaming, setStreaming] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError]         = useState('')
  const answerRef = useRef(null)
 
  // Load the list of indexed documents on first render
  useEffect(() => {
    loadSources()
  }, [])

  // Load the list of indexed documents on the first render
  useEffect(() => {
    loadSources()
  }, [])

  //Auto scroll the answer box as the token streams through
    useEffect(() => {
    if (answerRef.current) {
      answerRef.current.scrollTop = answerRef.current.scrollHeight
    }
  }, [answer])


  // -- API helpers --
   
  async function loadSources() {
    try{
      const res = await fetch(`${API}/sources`)
      const data = await res.json()
      setSources(data.sources || [])
    } catch (err) {
      console.error('Error loading sources:', err)
    }

  }


  async function uploadFile(e){
    const file = e.target.files[0]
    if (!file) return

    setUploading(true)
    setError('')

    const form = new FormData()
    form.append('file', file)

    try {
      const res = await fetch('${API}/ingest', {method:'POST', body: form})

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Upload failed')

      }

      const data = await res.json()
      alert(' Ingested "${data.source}"\n${data.chunks} chunks stored')
      loadSources()
    }catch (err) {
      console.error('Upload error:', err)
      setError(err.message)
    }

    setUploading(false)
    e.target.value = '' // reset file input so the same file can be uploaded again if needed
  }

  async function askQuestion() {
    if (!question.trim() || streaming) return
 
    setStreaming(true)
    setAnswer('')
    setError('')
 
    try {
      const res = await fetch(`${API}/query`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ question }),
      })
 
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || `Query failed (${res.status})`)
      }
 
      // Read the Server-Sent Events stream token by token
      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
 
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
 
        const chunk = decoder.decode(value)
 
        // Each SSE message is: "data: <token>\n\n"
        for (const line of chunk.split('\n\n')) {
          if (!line.startsWith('data: ')) continue
 
          const token = line.slice(6) // strip "data: " prefix
          if (token === '[DONE]') break
 
          // Unescape <br> that the backend used to encode newlines
          setAnswer(prev => prev + token.replace(/<br>/g, '\n'))
        }
      }
    } catch (err) {
      setError(err.message)
    }
 
    setStreaming(false)
  }
 
  async function deleteSource(name) {
    if (!confirm(`Remove "${name}" from the vector store?`)) return
    try {
      await fetch(`${API}/sources/${encodeURIComponent(name)}`, { method: 'DELETE' })
      loadSources()
    } catch (err) {
      setError(err.message)
    }
  }

  // -- render -----

  return(
    <div style={styles.layout}>
 
      {/* ── Sidebar ── */}
      <aside style={styles.sidebar}>
 
        <div style={styles.brand}>
          <h1 style={styles.brandTitle}>RAG Doc Reader</h1>
          <p style={styles.brandSub}>Powered by Ollama + ChromaDB</p>
        </div>
 
        {/* Upload */}
        <div>
          <p style={styles.sectionLabel}>UPLOAD DOCUMENT</p>
          <label
            style={{
              ...styles.uploadZone,
              color: uploading ? '#a5b4fc' : '#6b7280',
              cursor: uploading ? 'default' : 'pointer',
            }}
            onMouseEnter={e => { if (!uploading) e.currentTarget.style.borderColor = '#6366f1' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#d1d5db' }}
          >
            {uploading ? (
              'Indexing document...'
            ) : (
              <>
                Click to upload<br />
                <strong style={{ color: '#374151' }}>PDF · TXT · MD · DOCX</strong>
              </>
            )}
            <input
              type="file"
              accept=".pdf,.txt,.md,.markdown,.docx"
              onChange={uploadFile}
              disabled={uploading}
              style={{ display: 'none' }}
            />
          </label>
        </div>
 
        {/* Source list */}
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <p style={styles.sectionLabel}>LOADED DOCS</p>
            <button onClick={loadSources} style={styles.refreshBtn}>refresh</button>
          </div>
 
          <div style={styles.sourceList}>
            {sources.length === 0 ? (
              <p style={styles.emptyDocs}>No documents loaded yet</p>
            ) : (
              sources.map(src => (
                <div key={src} style={styles.sourceRow}>
                  <span style={styles.sourceName} title={src}>{src}</span>
                  <button
                    onClick={() => deleteSource(src)}
                    style={styles.deleteBtn}
                    title="Remove from vector store"
                  >
                    ×
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
 
      </aside>
 
      {/* ── Main chat area ── */}
      <main style={styles.main}>
 
        {/* Error banner */}
        {error && (
          <div style={styles.errorBanner}>
            <strong>Error:</strong> {error}
            <button onClick={() => setError('')} style={styles.errorClose}>×</button>
          </div>
        )}
 
        {/* Answer display */}
        <div ref={answerRef} style={styles.answerArea}>
          {answer ? (
            <div style={styles.answerBox}>
              {answer}
              {streaming && <span style={{ opacity: 0.4 }}>▌</span>}
            </div>
          ) : (
            <div style={styles.placeholder}>
              <div style={styles.placeholderIcon}>📄</div>
              <p>Upload a document, then ask anything about it</p>
              <p style={{ fontSize: 12, opacity: 0.6 }}>Answers are grounded in your document — no hallucination</p>
            </div>
          )}
        </div>
 
        {/* Input bar */}
        <div style={styles.inputBar}>
          <input
            value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && askQuestion()}
            placeholder="Ask a question about your documents... (Enter to send)"
            disabled={streaming}
            style={styles.input}
            onFocus={e => (e.target.style.borderColor = '#6366f1')}
            onBlur={e  => (e.target.style.borderColor = '#d1d5db')}
          />
          <button
            onClick={askQuestion}
            disabled={streaming || !question.trim()}
            style={{
              ...styles.askBtn,
              background: streaming || !question.trim() ? '#a5b4fc' : '#6366f1',
              cursor:     streaming || !question.trim() ? 'default' : 'pointer',
            }}
          >
            {streaming ? 'Thinking...' : 'Ask'}
          </button>
        </div>
 
      </main>
    </div>
  )

}

// --- Styling ---
