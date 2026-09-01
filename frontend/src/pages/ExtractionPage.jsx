import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { extractRun, listDocuments } from '../lib/api'
import { loadWorkspace, rememberExtraction } from '../lib/store'

export default function ExtractionPage() {
  const [ws, setWs] = useState(loadWorkspace())
  const [docs, setDocs] = useState([])
  const [form, setForm] = useState({ userId: '', documentId: '', templateId: '', backend: 'pgvector' })
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [result, setResult] = useState(null)

  useEffect(() => {
    setWs(loadWorkspace())
    listDocuments().then(d => {
      const w = loadWorkspace()
      setDocs(d.filter(x => !w.hiddenPdfIds.includes(x.id)))
    }).catch(() => [])
  }, [])

  const user = ws.users.find(u => u.id === form.userId)
  const doc = docs.find(d => d.id === form.documentId)
  const tpl = ws.templates.find(t => t.id === form.templateId)

  const ready = user && doc && tpl

  async function run() {
    setErr(''); setResult(null)
    if (!ready) { setErr('Please select a user, PDF, and template before running.'); return }
    setBusy(true)
    try {
      const data = await extractRun(doc.id, tpl.schema, `${tpl.name}.json`, form.backend)
      rememberExtraction(data.run_id, {
        userId: user.id, userName: user.name, purpose: user.purpose,
        documentId: doc.id, documentName: doc.filename,
        templateId: tpl.id, templateName: tpl.name,
        backend: form.backend,
      })
      setResult(data)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  const steps = [
    { label: 'Select User', done: !!user },
    { label: 'Choose PDF', done: !!doc },
    { label: 'Set Template', done: !!tpl },
    { label: 'Run', done: !!result },
  ]

  return (
    <>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Run Extraction</h1>
          <p>Select a user, PDF and template. The AI extracts structured fields from the document.</p>
        </div>
        <div className="page-header-actions">
          {!ws.users.length && <Link to="/users" className="btn">Add Users First</Link>}
          {!ws.templates.length && <Link to="/templates" className="btn">Add Templates First</Link>}
        </div>
      </div>

      <div className="steps" style={{marginBottom:24}}>
        {steps.map((s, i) => (
          <>
            <div key={s.label} className={`step ${s.done ? 'done' : i === steps.findIndex(x => !x.done) ? 'active' : ''}`}>
              <div className="step-num">
                {s.done ? (
                  <svg width="10" height="10" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/></svg>
                ) : i + 1}
              </div>
              {s.label}
            </div>
            {i < steps.length - 1 && <div className="step-sep" />}
          </>
        ))}
      </div>

      {err && <div className="alert error">{err}</div>}

      <div className="grid-2">
        <div style={{display:'flex', flexDirection:'column', gap:14}}>
          <div className="card">
            <div className="card-header">
              <div className="card-title">Configuration</div>
            </div>

            <div className="form-group">
              <label>User</label>
              <select value={form.userId} onChange={e => setForm({...form, userId: e.target.value})}>
                <option value="">— Select user —</option>
                {ws.users.map(u => <option key={u.id} value={u.id}>{u.name}{u.purpose ? ` · ${u.purpose}` : ''}</option>)}
              </select>
              {ws.users.length === 0 && (
                <div style={{fontSize:12,color:'var(--warning)',marginTop:4}}>
                  No users found. <Link to="/users" style={{color:'var(--accent)'}}>Add users →</Link>
                </div>
              )}
            </div>

            <div className="form-group">
              <label>PDF Document</label>
              <select value={form.documentId} onChange={e => setForm({...form, documentId: e.target.value})}>
                <option value="">— Select PDF —</option>
                {docs.map(d => <option key={d.id} value={d.id}>{d.filename}</option>)}
              </select>
              {docs.length === 0 && (
                <div style={{fontSize:12,color:'var(--warning)',marginTop:4}}>
                  No PDFs uploaded. <Link to="/pdfs" style={{color:'var(--accent)'}}>Upload one →</Link>
                </div>
              )}
            </div>

            <div className="form-group">
              <label>JSON Template</label>
              <select value={form.templateId} onChange={e => setForm({...form, templateId: e.target.value})}>
                <option value="">— Select template —</option>
                {ws.templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              {ws.templates.length === 0 && (
                <div style={{fontSize:12,color:'var(--warning)',marginTop:4}}>
                  No templates found. <Link to="/templates" style={{color:'var(--accent)'}}>Create one →</Link>
                </div>
              )}
            </div>

            <div className="form-group">
              <label>Search Backend</label>
              <select value={form.backend} onChange={e => setForm({...form, backend: e.target.value})}>
                <option value="pgvector">pgvector (default)</option>
                <option value="elasticsearch">Elasticsearch</option>
              </select>
              <div style={{fontSize:11.5,color:'var(--text-muted)',marginTop:4}}>
                This overrides the server default for this run.
              </div>
            </div>

            <button
              className="btn primary full lg"
              disabled={busy || !ready}
              onClick={run}
              style={{marginTop:4}}
            >
              {busy ? (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{animation:'spin 1s linear infinite'}}>
                    <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" opacity=".25"/>
                    <path d="M12 3a9 9 0 019 9"/>
                  </svg>
                  Running extraction…
                </>
              ) : 'Run Extraction'}
            </button>
          </div>
        </div>

        <div style={{display:'flex', flexDirection:'column', gap:14}}>
          <div className="card">
            <div className="card-header">
              <div className="card-title">Selected Mapping</div>
              <div className="card-subtitle text-muted">Preview before running</div>
            </div>

            {[
              { k: 'User', v: user?.name, sub: user?.purpose },
              { k: 'PDF', v: doc?.filename },
              { k: 'Template', v: tpl?.name, sub: tpl ? `${Object.keys(tpl.schema?.fields||{}).length} fields` : '' },
              { k: 'Backend', v: form.backend },
            ].map(({ k, v, sub }) => (
              <div key={k} className="info-row">
                <div className="info-row-label">{k}</div>
                <div className="info-row-value">
                  {v ? (
                    <div>
                      <div>{v}</div>
                      {sub && <div style={{fontSize:11.5,color:'var(--text-muted)',fontWeight:400}}>{sub}</div>}
                    </div>
                  ) : (
                    <span style={{color:'var(--text-muted)',fontWeight:400}}>Not selected</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {result && (
            <div className="card">
              <div className="card-header">
                <div className="card-title">Extraction Result</div>
                <span className="badge success">
                  {result.already_exists ? 'Cached' : 'New run'}
                </span>
              </div>

              <div className="alert success" style={{margin:'0 0 12px'}}>
                {result.already_exists ? 'Existing result reused from cache.' : 'Extraction complete — new result created.'}
              </div>

              <div className="code-preview">
                {JSON.stringify(result.result?.result || result.result, null, 2)}
              </div>

              <div style={{marginTop:12, display:'flex', gap:8}}>
                <Link className="btn primary" to={`/history?run=${result.run_id}`}>Open in History</Link>
                <Link className="btn" to="/compare">Compare Runs</Link>
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  )
}