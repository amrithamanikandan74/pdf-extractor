import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { listRuns } from '../lib/api'
import { loadWorkspace, deleteExtraction } from '../lib/store'

export default function HistoryPage() {
  const nav = useNavigate()
  const [params] = useSearchParams()
  const highlight = params.get('run')

  const [runs, setRuns] = useState([])
  const [ws, setWs] = useState(loadWorkspace())
  const [q, setQ] = useState('')
  const [selected, setSelected] = useState([])
  const [open, setOpen] = useState(highlight)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setWs(loadWorkspace())
    listRuns()
      .then(setRuns)
      .catch(() => [])
      .finally(() => setLoading(false))
  }, [])

  const filtered = useMemo(() => {
    return runs.filter((r) => {
      const m = ws.extractionMeta[r.run_id] || {}
      return (
        !q ||
        [
          r.document_filename,
          r.schema_name,
          m.userName,
          m.purpose,
          m.backend,
          JSON.stringify(r.result),
        ]
          .join(' ')
          .toLowerCase()
          .includes(q.toLowerCase())
      )
    })
  }, [runs, q, ws])

  function toggle(id) {
    setSelected((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : prev.length === 2
          ? [prev[1], id]
          : [...prev, id]
    )
  }

  function handleDelete(runId) {
    const confirmDelete = window.confirm(
      'Are you sure you want to delete this extraction from the UI history?'
    )

    if (!confirmDelete) return

    deleteExtraction(runId)
    setWs(loadWorkspace())
    setRuns((prev) => prev.filter((r) => r.run_id !== runId))
    setSelected((prev) => prev.filter((id) => id !== runId))

    if (open === runId) {
      setOpen(null)
    }
  }

  const opened = open ? runs.find((r) => r.run_id === open) : null

  if (opened) {
    const m = ws.extractionMeta[opened.run_id] || {}

    return (
      <>
        <div className="page-header">
          <div className="page-header-left">
            <h1>{opened.document_filename}</h1>
            <p>
              {m.userName || 'No user'} · {m.templateName || opened.schema_name} ·{' '}
              {m.backend || 'default backend'}
            </p>
          </div>

          <div className="page-header-actions">
            <button className="btn" onClick={() => setOpen(null)}>
              Back to History
            </button>

            <Link className="btn primary" to={`/compare?left=${opened.run_id}`}>
              Use in Compare
            </Link>

            <button className="btn danger" onClick={() => handleDelete(opened.run_id)}>
              Delete
            </button>
          </div>
        </div>

        <div className="grid-2">
          <div className="card">
            <div className="card-header">
              <div className="card-title">Run Information</div>
            </div>

            {[
              { k: 'Run ID', v: opened.run_id },
              { k: 'User', v: m.userName },
              { k: 'Purpose', v: m.purpose },
              { k: 'PDF', v: opened.document_filename },
              { k: 'Template', v: m.templateName || opened.schema_name },
              { k: 'Backend', v: m.backend },
              { k: 'Date', v: new Date(opened.created_at).toLocaleString() },
            ].map(({ k, v }) => (
              <div key={k} className="info-row">
                <div className="info-row-label">{k}</div>
                <div
                  className="info-row-value"
                  style={{
                    fontFamily: k === 'Run ID' ? 'var(--font-mono, DM Mono)' : 'inherit',
                    fontSize: k === 'Run ID' ? 11 : 13.5,
                  }}
                >
                  {v || '—'}
                </div>
              </div>
            ))}
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title">Extracted Result</div>
            </div>

            <div className="code-preview" style={{ maxHeight: 420 }}>
              {JSON.stringify(opened.result?.result || opened.result, null, 2)}
            </div>
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Extraction History</h1>
          <p>Full audit trail. Search by user, PDF, template, backend, or result content.</p>
        </div>

        <div className="page-header-actions">
          <span className="badge neutral">{runs.length} runs</span>

          <button
            className="btn primary"
            disabled={selected.length !== 2}
            onClick={() => nav(`/compare?left=${selected[0]}&right=${selected[1]}`)}
          >
            Compare ({selected.length}/2)
          </button>
        </div>
      </div>

      <div className="toolbar">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by user, PDF, template, backend…"
          style={{ maxWidth: 360 }}
        />

        {selected.length > 0 && (
          <span className="badge info">
            {selected.length} selected — select {2 - selected.length} more to compare
          </span>
        )}
      </div>

      <div className="card" style={{ padding: 0 }}>
        {loading ? (
          <div className="empty-state">
            <p>Loading runs…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <p>{q ? 'No results match your search.' : 'No extraction runs yet.'}</p>
            {!q && (
              <Link to="/extract" style={{ color: 'var(--accent)', fontSize: 13 }}>
                Run your first extraction
              </Link>
            )}
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 40 }}></th>
                  <th>User</th>
                  <th>PDF Document</th>
                  <th>Template</th>
                  <th>Backend</th>
                  <th>Status</th>
                  <th>Date</th>
                  <th style={{ width: 150 }}>Actions</th>
                </tr>
              </thead>

              <tbody>
                {filtered.map((r) => {
                  const m = ws.extractionMeta[r.run_id] || {}
                  const isSelected = selected.includes(r.run_id)

                  return (
                    <tr key={r.run_id} style={isSelected ? { background: 'var(--accent-light)' } : {}}>
                      <td>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggle(r.run_id)}
                          style={{ cursor: 'pointer' }}
                        />
                      </td>

                      <td>
                        <span style={{ fontWeight: 500 }}>{m.userName || 'No user'}</span>
                        {m.purpose && (
                          <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
                            {m.purpose}
                          </div>
                        )}
                      </td>

                      <td>
                        <div
                          style={{
                            fontSize: 13,
                            maxWidth: 180,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {r.document_filename}
                        </div>
                      </td>

                      <td>{m.templateName || r.schema_name}</td>

                      <td>
                        <span className="badge neutral">{m.backend || 'default'}</span>
                      </td>

                      <td>
                        {r.status === 'completed' && <span className="badge success">Completed</span>}
                        {r.status === 'pending' && <span className="badge warning">Pending…</span>}
                        {r.status === 'failed' && (
                          <span className="badge danger" title={r.error_message || 'Extraction failed'}>Failed</span>
                        )}
                        {!r.status && <span className="badge success">Completed</span>}
                      </td>

                      <td style={{ fontSize: 12.5, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {new Date(r.created_at).toLocaleString()}
                      </td>

                      <td>
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn sm" onClick={() => setOpen(r.run_id)}>
                            View
                          </button>

                          <button className="btn sm danger" onClick={() => handleDelete(r.run_id)}>
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}