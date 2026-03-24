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



}
