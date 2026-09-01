import { Link } from 'react-router-dom'
import { loadWorkspace } from '../lib/store'

export default function DashboardPage() {
  const ws = loadWorkspace()
  const pdfCount = ws.pdfs?.length || 0
  const templateCount = ws.templates?.length || 0
  const runCount = ws.mappings?.length || 0
  const userCount = ws.users?.length || 0

  const recent = ws.mappings?.slice(0, 5).reverse() || []

  const actions = [
    { to: '/users', label: 'Add user', sub: 'Create user and purpose', color: '#edf0fe' },
    { to: '/pdfs', label: 'Upload PDF', sub: 'Add documents to your library', color: '#ecfdf5' },
    { to: '/templates', label: 'Upload template', sub: 'Define what fields to extract', color: '#fffbeb' },
    { to: '/extract', label: 'Run extraction', sub: 'Map user, PDF, template and backend', color: '#fef2f2' },
    { to: '/history', label: 'Review results', sub: 'View history and compare runs', color: '#f8fafc' },
  ]

  return (
    <>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Welcome back</h1>
          <p>Manage your document pipeline and extract structured data with AI.</p>
        </div>
        <div className="page-header-actions">
          <Link to="/pdfs" className="btn primary">Upload PDF</Link>
          <Link to="/extract" className="btn">Run Extraction</Link>
        </div>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-label">Total Documents</div>
          <div className="stat-value">{pdfCount}</div>
          <div className="stat-change">PDFs uploaded</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Templates</div>
          <div className="stat-value">{templateCount}</div>
          <div className="stat-change">JSON schemas</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Extraction Runs</div>
          <div className="stat-value">{runCount}</div>
          <div className="stat-change">Completed</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Users</div>
          <div className="stat-value">{userCount}</div>
          <div className="stat-change">Active accounts</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Recent Extractions</div>
              <div className="card-subtitle">Latest extraction runs</div>
            </div>
            <Link to="/history" className="btn sm">View all</Link>
          </div>

          {recent.length === 0 ? (
            <div className="empty-state">
              <p>No extractions yet. <Link to="/extract" style={{ color: 'var(--accent)' }}>Run one now</Link></p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Template</th>
                    <th>User</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((m, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 500 }}>{m.documentName || '—'}</td>
                      <td>{m.templateName || '—'}</td>
                      <td>{m.userName || '—'}</td>
                      <td><span className="badge success">Completed</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Workflow</div>
              <div className="card-subtitle">Follow the steps in order</div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {actions.map((a, index) => (
              <Link
                key={a.to}
                to={a.to}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 12px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  textDecoration: 'none',
                  transition: 'all 0.15s',
                  background: 'var(--surface)',
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--surface-2)'}
                onMouseLeave={e => e.currentTarget.style.background = 'var(--surface)'}
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 8,
                    background: a.color,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 13,
                    fontWeight: 600,
                    color: 'var(--text-secondary)',
                    flexShrink: 0,
                  }}
                >
                  {index + 1}
                </div>

                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                    {a.label}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    {a.sub}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}