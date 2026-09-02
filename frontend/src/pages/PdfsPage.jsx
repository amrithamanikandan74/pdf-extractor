import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL, getDocument, getDocumentChunks, listDocuments, uploadPdf } from '../lib/api'
import { hidePdf, loadWorkspace } from '../lib/store'

export default function PdfsPage() {
  const fileRef = useRef(null)
  const [docs, setDocs] = useState([])
  const [ws, setWs] = useState(loadWorkspace())
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [chunks, setChunks] = useState([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [progress, setProgress] = useState(0)
  const [backendDown, setBackendDown] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [previewTab, setPreviewTab] = useState('preview') // 'preview' | 'text' | 'chunks'
  const [iframeLoaded, setIframeLoaded] = useState(false)

  async function load() {
    try {
      const data = await listDocuments()
      const workspace = loadWorkspace()
      setWs(workspace)
      setDocs(data.filter((doc) => !workspace.hiddenPdfIds.includes(doc.id)))
      setBackendDown(false)
    } catch {
      setBackendDown(true)
      setDocs([])
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function upload(file) {
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setErr('Please upload a PDF file only.')
      return
    }

    setBusy(true)
    setErr('')
    setProgress(10)

    // Simulate progress stages
    const progressTimer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 85) {
          clearInterval(progressTimer)
          return prev
        }
        return prev + Math.random() * 15
      })
    }, 400)

    try {
      const uploaded = await uploadPdf(file)
      clearInterval(progressTimer)
      setProgress(100)
      await load()

      const uploadedDoc = {
        id: uploaded.document_id || uploaded.id,
        filename: uploaded.filename || file.name,
      }

      await openPdf(uploadedDoc)
      setTimeout(() => setProgress(0), 1000)
    } catch (e) {
      clearInterval(progressTimer)
      setErr(e.message)
      setProgress(0)
    } finally {
      setBusy(false)
    }
  }

  async function openPdf(doc) {
    setSelected(doc)
    setDetail(null)
    setChunks([])
    setPreviewTab('preview')
    setIframeLoaded(false)

    try {
      const docDetail = await getDocument(doc.id)
      const chunkData = await getDocumentChunks(doc.id)
      setDetail(docDetail)
      setChunks(chunkData.chunks || [])
    } catch (e) {
      setErr(e.message)
    }
  }

  function closePreview() {
    setSelected(null)
    setDetail(null)
    setChunks([])
    setIframeLoaded(false)
  }

  function removePdf(id) {
    hidePdf(id)

    if (selected?.id === id) {
      closePreview()
    }

    load()
  }

  function downloadPdf() {
    if (!selected) return
    const link = document.createElement('a')
    link.href = `${API_BASE_URL}/documents/${selected.id}/file`
    link.download = selected.filename
    link.click()
  }

  function openInNewTab() {
    if (!selected) return
    window.open(`${API_BASE_URL}/documents/${selected.id}/file`, '_blank')
  }

  const extractionCount = (id) =>
    (ws.mappings || []).filter((item) => item.documentId === id).length

  const totalPages = detail?.extracted_text
    ? (detail.extracted_text.match(/Page \d+:/g) || []).length
    : 0

  const textLength = detail?.extracted_text?.length || 0

  return (
    <>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Documents</h1>
          <p>Upload a PDF and preview it before running extraction.</p>
        </div>

        <div className="page-header-actions">
          <span className="badge info">{docs.length} documents</span>

          <button
            className="btn primary"
            onClick={() => fileRef.current.click()}
            disabled={busy}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            Upload PDF
          </button>

          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            hidden
            onChange={(e) => {
              upload(e.target.files[0])
              e.target.value = ''
            }}
          />
        </div>
      </div>

      {/* Backend connection error */}
      {backendDown && (
        <div className="alert error" style={{ marginBottom: 16 }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, marginTop: 1 }}>
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <div>
            <strong>Backend not connected</strong> — Cannot reach the API at <code style={{ fontSize: 12 }}>{API_BASE_URL}</code>.
            Start the backend server to upload and view PDFs.
            <button className="btn sm" style={{ marginLeft: 10 }} onClick={load}>Retry</button>
          </div>
        </div>
      )}

      {err && <div className="alert error">{err}</div>}

      {/* Upload progress bar */}
      {progress > 0 && (
        <div className="pdf-progress-wrap">
          <div className="pdf-progress-header">
            <span className="pdf-progress-label">
              {progress < 100 ? '⬆ Uploading & processing PDF...' : '✓ Upload complete'}
            </span>
            <span className="pdf-progress-pct">{Math.round(progress)}%</span>
          </div>
          <div className="progress-bar" style={{ height: 6 }}>
            <div className="progress-fill" style={{ width: `${progress}%`, transition: 'width 0.4s ease' }} />
          </div>
        </div>
      )}

      <div className="pdf-layout">
        {/* Left column: Upload + List */}
        <div className="pdf-left-col">
          {/* Drag & Drop Zone */}
          <div
            className={`upload-drop${dragging ? ' upload-drop-active' : ''}${busy ? ' upload-drop-busy' : ''}`}
            onClick={() => !busy && fileRef.current.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragging(false)
              upload(e.dataTransfer.files[0])
            }}
          >
            <div className="upload-drop-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="12" y1="18" x2="12" y2="12" />
                <line x1="9" y1="15" x2="12" y2="12" />
                <line x1="15" y1="15" x2="12" y2="12" />
              </svg>
            </div>
            <h3>{busy ? 'Processing PDF...' : dragging ? 'Drop to upload' : 'Drop a PDF here'}</h3>
            <p>or click to browse · PDF files only · Max 10 MB</p>
          </div>

          {/* Uploaded PDFs List */}
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Uploaded PDFs</div>
                <div className="card-subtitle">
                  {docs.length} document{docs.length !== 1 ? 's' : ''} available
                </div>
              </div>
            </div>

            {docs.length === 0 ? (
              <div className="empty-state" style={{ minHeight: 120, padding: '32px 24px' }}>
                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.3 }}>
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <p>{backendDown ? 'Start backend to see PDFs' : 'No PDFs uploaded yet.'}</p>
              </div>
            ) : (
              <div className="pdf-list">
                {docs.map((doc) => (
                  <div
                    className={`pdf-list-item${selected?.id === doc.id ? ' pdf-list-item-active' : ''}`}
                    key={doc.id}
                    onClick={() => openPdf(doc)}
                  >
                    <div className="pdf-list-item-icon">
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                    </div>

                    <div className="pdf-list-item-info">
                      <div className="pdf-list-item-name">{doc.filename}</div>
                      <div className="pdf-list-item-meta">
                        {extractionCount(doc.id)} extraction{extractionCount(doc.id) !== 1 ? 's' : ''}
                      </div>
                    </div>

                    <div className="record-row-actions" onClick={(e) => e.stopPropagation()}>
                      <button className="btn sm" onClick={() => openPdf(doc)}>
                        View
                      </button>
                      <button className="btn sm danger" onClick={() => removePdf(doc.id)}>
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right column: Preview Panel */}
        <div className="pdf-preview-panel">
          {!selected ? (
            <div className="pdf-preview-empty">
              <div className="pdf-preview-empty-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
              </div>
              <h3>No PDF selected</h3>
              <p>Upload or select a PDF to preview it here</p>
            </div>
          ) : (
            <>
              {/* Preview Header */}
              <div className="pdf-preview-header">
                <div className="pdf-preview-header-left">
                  <div className="pdf-preview-filename">{selected.filename}</div>
                  <div className="pdf-preview-stats">
                    {totalPages > 0 && <span className="tag">{totalPages} pages</span>}
                    {chunks.length > 0 && <span className="tag">{chunks.length} chunks</span>}
                    {textLength > 0 && (
                      <span className="tag">{(textLength / 1024).toFixed(1)} KB text</span>
                    )}
                  </div>
                </div>

                <div className="pdf-preview-header-actions">
                  <button className="btn sm" onClick={openInNewTab} title="Open in new tab">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                      <polyline points="15 3 21 3 21 9" />
                      <line x1="10" y1="14" x2="21" y2="3" />
                    </svg>
                    Open
                  </button>
                  <button className="btn sm" onClick={downloadPdf} title="Download PDF">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    Download
                  </button>
                  <button className="btn sm danger" onClick={closePreview} title="Close preview">
                    ✕
                  </button>
                </div>
              </div>

              {/* Tab Navigation */}
              <div className="pdf-preview-tabs">
                <button
                  className={`pdf-tab${previewTab === 'preview' ? ' pdf-tab-active' : ''}`}
                  onClick={() => setPreviewTab('preview')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                  Preview
                </button>
                <button
                  className={`pdf-tab${previewTab === 'text' ? ' pdf-tab-active' : ''}`}
                  onClick={() => setPreviewTab('text')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="17" y1="10" x2="3" y2="10" />
                    <line x1="21" y1="6" x2="3" y2="6" />
                    <line x1="21" y1="14" x2="3" y2="14" />
                    <line x1="17" y1="18" x2="3" y2="18" />
                  </svg>
                  Extracted Text
                </button>
                <button
                  className={`pdf-tab${previewTab === 'chunks' ? ' pdf-tab-active' : ''}`}
                  onClick={() => setPreviewTab('chunks')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="7" height="7" />
                    <rect x="14" y="3" width="7" height="7" />
                    <rect x="3" y="14" width="7" height="7" />
                    <rect x="14" y="14" width="7" height="7" />
                  </svg>
                  Chunks
                  {chunks.length > 0 && (
                    <span className="pdf-tab-count">{chunks.length}</span>
                  )}
                </button>
              </div>

              {/* Tab Content */}
              <div className="pdf-preview-body">
                {previewTab === 'preview' && (
                  <div className="pdf-iframe-wrap">
                    {!iframeLoaded && (
                      <div className="pdf-iframe-loading">
                        <div className="pdf-spinner" />
                        <span>Loading PDF...</span>
                      </div>
                    )}
                    <iframe
                      src={`${API_BASE_URL}/documents/${selected.id}/file#toolbar=1&navpanes=0&scrollbar=1&view=FitH`}
                      title={selected.filename}
                      onLoad={() => setIframeLoaded(true)}
                      className="pdf-iframe"
                    />
                  </div>
                )}

                {previewTab === 'text' && (
                  <div className="pdf-text-view">
                    {detail?.extracted_text ? (
                      <>
                        <div className="pdf-text-header">
                          <span className="text-muted">
                            {textLength.toLocaleString()} characters · {totalPages} pages
                          </span>
                          <button
                            className="btn sm"
                            onClick={() => {
                              navigator.clipboard.writeText(detail.extracted_text)
                            }}
                          >
                            Copy All
                          </button>
                        </div>
                        <pre className="pdf-text-content">{detail.extracted_text}</pre>
                      </>
                    ) : (
                      <div className="empty-state" style={{ minHeight: 200 }}>
                        <p>Loading extracted text...</p>
                      </div>
                    )}
                  </div>
                )}

                {previewTab === 'chunks' && (
                  <div className="pdf-chunks-view">
                    {chunks.length === 0 ? (
                      <div className="empty-state" style={{ minHeight: 200 }}>
                        <p>No chunks available.</p>
                      </div>
                    ) : (
                      <>
                        <div className="pdf-text-header">
                          <span className="text-muted">{chunks.length} chunks extracted</span>
                        </div>
                        <div className="pdf-chunks-list">
                          {chunks.map((chunk) => (
                            <div className="pdf-chunk-card" key={chunk.chunk_index}>
                              <div className="pdf-chunk-header">
                                <span className="pdf-chunk-index">#{chunk.chunk_index}</span>
                                <span className="pdf-chunk-page">Page {chunk.page_number}</span>
                                {chunk.heading && (
                                  <span className="pdf-chunk-heading">{chunk.heading}</span>
                                )}
                              </div>
                              <div className="pdf-chunk-text">{chunk.chunk_text}</div>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}