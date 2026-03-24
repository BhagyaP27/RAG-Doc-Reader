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
}
