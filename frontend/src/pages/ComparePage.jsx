import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { compareRuns } from '../lib/api'
import { loadWorkspace } from '../lib/store'

function fmt(value) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

function normalizeText(value) {
  if (value === null || value === undefined) return ''

  if (Array.isArray(value)) {
    return value
      .map((item) => normalizeText(item))
      .sort()
      .join('|')
  }

  if (typeof value === 'object') {
    return Object.keys(value)
      .sort()
      .map((key) => `${key}:${normalizeText(value[key])}`)
      .join('|')
  }

  return String(value)
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .replace(/[.,;:()[\]{}"'`]/g, '')
    .trim()
}

function getSmartStatus(a, b) {
  const left = normalizeText(a)
  const right = normalizeText(b)

  if (left === right) return 'matched'

  if (left && right && (left.includes(right) || right.includes(left))) {
    return 'partial'
  }

  return 'mismatched'
}

function StatusBadge({ status }) {
  if (status === 'matched') {
    return <span className="badge matched">Match</span>
  }

  if (status === 'partial') {
    return <span className="badge warning">Partial</span>
  }

  return <span className="badge mismatched">Mismatch</span>
}

export default function ComparePage() {
  const [params] = useSearchParams()
  const left = params.get('left')
  const right = params.get('right')

  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)

  const ws = loadWorkspace()

  useEffect(() => {
    if (left && right) {
      setLoading(true)
      setErr('')

      compareRuns(left, right)
        .then(setData)
        .catch((e) => setErr(e.message))
        .finally(() => setLoading(false))
    }
  }, [left, right])

  const smartComparison = useMemo(() => {
    if (!data?.comparison) return []

    return data.comparison.map((row) => ({
      ...row,
      smartStatus: getSmartStatus(row.run1_value, row.run2_value),
    }))
  }, [data])

  const summary = useMemo(() => {
    const total = smartComparison.length
    const matched = smartComparison.filter((row) => row.smartStatus === 'matched').length
    const partial = smartComparison.filter((row) => row.smartStatus === 'partial').length
    const mismatched = smartComparison.filter((row) => row.smartStatus === 'mismatched').length

    const accuracy = total
      ? Math.round(((matched + partial * 0.5) / total) * 100)
      : 0

    return {
      total,
      matched,
      partial,
      mismatched,
      accuracy,
    }
  }, [smartComparison])

  if (!left || !right) {
    return (
      <>
        <div className="page-header">
          <div className="page-header-left">
            <h1>Compare Runs</h1>
            <p>Select two extraction runs from History to compare them field by field.</p>
          </div>
        </div>

        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>
            No runs selected
          </h2>

          <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>
            Go to History, check two extraction runs, then click Compare.
          </p>

          <Link className="btn primary" to="/history">
            Open History
          </Link>
        </div>
      </>
    )
  }

  const m1 = ws.extractionMeta[left] || {}
  const m2 = ws.extractionMeta[right] || {}

  return (
    <>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Version Comparison</h1>
          <p>Field-by-field comparison of two extraction runs.</p>
        </div>

        <div className="page-header-actions">
          <Link className="btn" to="/history">
            Back to History
          </Link>
        </div>
      </div>

      {err && <div className="alert error">{err}</div>}
      {loading && <div className="alert info">Loading comparison data...</div>}

      {data && (
        <>
          <div className="stats-grid" style={{ marginBottom: 20 }}>
            <div className="stat-card">
              <div className="stat-label">Accuracy</div>
              <div
                className="stat-value"
                style={{
                  color:
                    summary.accuracy >= 80
                      ? 'var(--accent-2)'
                      : summary.accuracy >= 50
                        ? 'var(--warning)'
                        : 'var(--danger)',
                }}
              >
                {summary.accuracy}%
              </div>

              <div className="progress-bar" style={{ marginTop: 6 }}>
                <div
                  className="progress-fill"
                  style={{
                    width: `${summary.accuracy}%`,
                    background:
                      summary.accuracy >= 80
                        ? 'var(--accent-2)'
                        : summary.accuracy >= 50
                          ? 'var(--warning)'
                          : 'var(--danger)',
                  }}
                />
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-label">Matched</div>
              <div className="stat-value" style={{ color: 'var(--accent-2)' }}>
                {summary.matched}
              </div>
              <div className="stat-change">Same values</div>
            </div>

            <div className="stat-card">
              <div className="stat-label">Partial</div>
              <div className="stat-value" style={{ color: 'var(--warning)' }}>
                {summary.partial}
              </div>
              <div className="stat-change">Similar values</div>
            </div>

            <div className="stat-card">
              <div className="stat-label">Mismatched</div>
              <div className="stat-value" style={{ color: 'var(--danger)' }}>
                {summary.mismatched}
              </div>
              <div className="stat-change">Different values</div>
            </div>
          </div>

          <div className="grid-2" style={{ marginBottom: 16 }}>
            <div className="card">
              <div className="card-header">
                <div className="card-title">Run A</div>
                <span className="badge info">Left</span>
              </div>

              {[
                { k: 'User', v: m1.userName },
                { k: 'PDF', v: data.run1.document_filename },
                { k: 'Template', v: m1.templateName || data.run1.schema_name },
                { k: 'Backend', v: m1.backend },
              ].map(({ k, v }) => (
                <div key={k} className="info-row">
                  <div className="info-row-label">{k}</div>
                  <div className="info-row-value">{v || '—'}</div>
                </div>
              ))}
            </div>

            <div className="card">
              <div className="card-header">
                <div className="card-title">Run B</div>
                <span className="badge neutral">Right</span>
              </div>

              {[
                { k: 'User', v: m2.userName },
                { k: 'PDF', v: data.run2.document_filename },
                { k: 'Template', v: m2.templateName || data.run2.schema_name },
                { k: 'Backend', v: m2.backend },
              ].map(({ k, v }) => (
                <div key={k} className="info-row">
                  <div className="info-row-label">{k}</div>
                  <div className="info-row-value">{v || '—'}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="card" style={{ padding: 0 }}>
            <div style={{ padding: '16px 20px 12px', borderBottom: '1px solid var(--border)' }}>
              <div className="card-title">Field-by-Field Comparison</div>
            </div>

            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th style={{ width: '18%' }}>Field</th>
                    <th style={{ width: '36%' }}>Run A Value</th>
                    <th style={{ width: '36%' }}>Run B Value</th>
                    <th style={{ width: '10%' }}>Status</th>
                  </tr>
                </thead>

                <tbody>
                  {smartComparison.map((row) => (
                    <tr
                      key={row.field}
                      style={
                        row.smartStatus === 'mismatched'
                          ? { background: '#fff5f5' }
                          : row.smartStatus === 'partial'
                            ? { background: '#fffbeb' }
                            : {}
                      }
                    >
                      <td
                        style={{
                          fontFamily: 'DM Mono, monospace',
                          fontSize: 12.5,
                          fontWeight: 500,
                        }}
                      >
                        {row.field}
                      </td>

                      <td>
                        <pre
                          style={{
                            background: 'none',
                            padding: 0,
                            fontSize: 12.5,
                            color: 'var(--text-primary)',
                            whiteSpace: 'pre-wrap',
                          }}
                        >
                          {fmt(row.run1_value)}
                        </pre>
                      </td>

                      <td>
                        <pre
                          style={{
                            background: 'none',
                            padding: 0,
                            fontSize: 12.5,
                            color: 'var(--text-primary)',
                            whiteSpace: 'pre-wrap',
                          }}
                        >
                          {fmt(row.run2_value)}
                        </pre>
                      </td>

                      <td>
                        <StatusBadge status={row.smartStatus} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  )
}