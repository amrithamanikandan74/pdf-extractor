import { useEffect, useRef, useState } from 'react'
import { listDocuments, searchDocument } from '../lib/api'
import { loadWorkspace } from '../lib/store'
import { Link } from 'react-router-dom'

export default function ChatbotPage() {
  const [docs, setDocs] = useState([])
  const [doc, setDoc] = useState('')
  const [q, setQ] = useState('')
  const [answers, setAnswers] = useState([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => {
    listDocuments().then(d => {
      const w = loadWorkspace()
      setDocs(d.filter(x => !w.hiddenPdfIds.includes(x.id)))
    }).catch(() => [])
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [answers])

  async function ask(e) {
    e.preventDefault()
    if (!doc || !q.trim()) return
    setBusy(true); setErr('')
    const question = q
    setQ('')
    try {
      const data = await searchDocument(doc, question)
      const chunks = data.results || data.chunks || data || []
      setAnswers(p => [...p, { q: question, chunks: Array.isArray(chunks) ? chunks : [chunks], ts: new Date() }])
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  const selectedDoc = docs.find(d => d.id === doc)

  return (
    <>
      <div className="page-header">
        <div className="page-header-left">
          <h1>AI Assistant</h1>
          <p>Ask questions about any uploaded PDF using semantic search.</p>
        </div>
        <div className="page-header-actions">
          {docs.length === 0 && <Link to="/pdfs" className="btn">Upload a PDF first</Link>}
        </div>
      </div>

      <div className="grid-2" style={{alignItems:'start'}}>
        <div style={{display:'flex', flexDirection:'column', gap:14}}>
          <div className="card">
            <div className="card-header">
              <div className="card-title">Select Document</div>
            </div>

            <div className="form-group" style={{marginBottom:0}}>
              <label>PDF to query</label>
              <select value={doc} onChange={e => setDoc(e.target.value)}>
                <option value="">— Choose a document —</option>
                {docs.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
              </select>
            </div>

            {selectedDoc && (
              <div style={{marginTop:12,padding:'10px 12px',background:'var(--accent-light)',borderRadius:'var(--radius-sm)'}}>
                <div style={{fontSize:12.5,color:'var(--accent-dark)',fontWeight:600}}>Active document</div>
                <div style={{fontSize:13,color:'var(--text-primary)',marginTop:2}}>{selectedDoc.filename}</div>
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Ask a Question</div>
            </div>
            <form onSubmit={ask} style={{display:'flex',flexDirection:'column',gap:8}}>
              <textarea
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="e.g. What is the invoice total? Who is the vendor? What are the payment terms?"
                disabled={!doc || busy}
                style={{minHeight:90, fontFamily:'inherit', fontSize:13.5, resize:'vertical'}}
                onKeyDown={e => { if (e.key==='Enter' && e.metaKey) ask(e) }}
              />
              <button className="btn primary full" disabled={busy || !doc || !q.trim()}>
                {busy ? 'Searching…' : 'Ask'}
              </button>
              <div className="text-muted" style={{textAlign:'center', fontSize:11.5}}>⌘ + Enter to send</div>
            </form>
          </div>
        </div>

        <div className="card" style={{minHeight:400}}>
          <div className="card-header">
            <div className="card-title">Results</div>
            {answers.length > 0 && (
              <button className="btn sm" onClick={() => setAnswers([])}>Clear</button>
            )}
          </div>

          {err && <div className="alert error">{err}</div>}

          {answers.length === 0 && !busy ? (
            <div className="empty-state">
              <svg viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clipRule="evenodd"/></svg>
              <p>Select a PDF and ask a question to get started.</p>
            </div>
          ) : (
            <div className="chat-wrap">
              {answers.map((a, i) => (
                <div key={i} className="answer-item">
                  <div className="answer-q">
                    <div style={{
                      width:22,height:22,borderRadius:50,background:'var(--accent)',
                      color:'white',display:'flex',alignItems:'center',justifyContent:'center',
                      fontSize:11,fontWeight:700,flexShrink:0
                    }}>Q</div>
                    {a.q}
                    <span className="text-muted" style={{marginLeft:'auto',fontSize:11,whiteSpace:'nowrap'}}>
                      {a.ts.toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="answer-body" style={{marginLeft:30}}>
                    {a.chunks[0]?.chunk_text || a.chunks[0]?.text || JSON.stringify(a.chunks[0] || {})}
                  </div>
                  {a.chunks.length > 1 && (
                    <details style={{marginLeft:30}}>
                      <summary>View {a.chunks.length - 1} more source chunks</summary>
                      <div style={{marginTop:8,display:'flex',flexDirection:'column',gap:6}}>
                        {a.chunks.slice(1, 4).map((c, j) => (
                          <div key={j} className="chunk-item">
                            <div className="chunk-text">{c.chunk_text || c.text || JSON.stringify(c, null, 2)}</div>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              ))}
              {busy && (
                <div className="answer-item" style={{opacity:0.6}}>
                  <div className="answer-q">
                    <div style={{width:22,height:22,borderRadius:50,background:'var(--surface-2)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:11,fontWeight:700}}>…</div>
                    Searching…
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </div>
    </>
  )
}