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

  async function load() {
    const data = await listDocuments().catch(() => [])
    const workspace = loadWorkspace()
    setWs(workspace)
    setDocs(data.filter((doc) => !workspace.hiddenPdfIds.includes(doc.id)))
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
    setProgress(20)

    try {
      const uploaded = await uploadPdf(file)
      setProgress(100)
      await load()

      const uploadedDoc = {
        id: uploaded.document_id || uploaded.id,
        filename: uploaded.filename || file.name,
      }

      await openPdf(uploadedDoc)
      setTimeout(() => setProgress(0), 800)
    } catch (e) {
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
  }

  function removePdf(id) {
    hidePdf(id)

    if (selected?.id === id) {
      closePreview()
    }

    load()
  }

  const extractionCount = (id) =>
    (ws.mappings || []).filter((item) => item.documentId === id).length

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
            Upload PDF
          </button>

          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            hidden
            onChange={(e) => upload(e.target.files[0])}
          />
        </div>
      </div>

      {err && <div className="alert error">{err}</div>}

      {progress > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span className="text-muted">
              {progress < 100 ? 'Uploading PDF...' : 'Upload complete'}
            </span>
            <span className="text-muted">{progress}%</span>
          </div>

          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      <div className="grid-2" style={{ alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div
            className="upload-drop"
            onClick={() => fileRef.current.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault()
              upload(e.dataTransfer.files[0])
            }}
          >
            <h3>{busy ? 'Processing PDF...' : 'Drop a PDF here'}</h3>
            <p>or click to browse · PDF files only</p>
          </div>

          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">Uploaded PDFs</div>
                <div className="card-subtitle">
                  {docs.length} document{docs.length !== 1 ? 's' : ''}
                </div>
              </div>
            </div>

            {docs.length === 0 ? (
              <div className="empty-state">
                <p>No PDFs uploaded yet.</p>
              </div>
            ) : (
              docs.map((doc) => (
                <div className="record-row" key={doc.id}>
                  <div className="record-row-left">
                    <div>
                      <div className="record-row-name">{doc.filename}</div>
                      <div className="record-row-sub">
                        {extractionCount(doc.id)} extraction
                        {extractionCount(doc.id) !== 1 ? 's' : ''}
                      </div>
                    </div>
                  </div>

                  <div className="record-row-actions">
                    <button className="btn sm" onClick={() => openPdf(doc)}>
                      View
                    </button>

                    <button className="btn sm danger" onClick={() => removePdf(doc.id)}>
                      Remove
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="card" style={{ minHeight: 420 }}>
          <div className="card-header">
            <div>
              <div className="card-title">PDF Preview</div>
              <div className="card-subtitle">
                {selected ? selected.filename : 'Upload or select a PDF'}
              </div>
            </div>

            {selected && (
              <button className="btn sm" onClick={closePreview}>
                Close
              </button>
            )}
          </div>

          {!selected ? (
            <div className="empty-state" style={{ minHeight: 300 }}>
              <p>After upload, the PDF will appear here automatically.</p>
            </div>
          ) : (
            <>
              <iframe
                src={`${API_BASE_URL}/documents/${selected.id}/file#toolbar=0&navpanes=0&scrollbar=1`}
                title={selected.filename}
                style={{
                  width: '100%',
                  height: '360px',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  background: '#ffffff',
                }}
              />

              <div style={{ marginTop: 12 }}>
                <div className="info-row">
                  <div className="info-row-label">File name</div>
                  <div className="info-row-value">{selected.filename}</div>
                </div>

                <div className="info-row">
                  <div className="info-row-label">Chunks created</div>
                  <div className="info-row-value">{chunks.length}</div>
                </div>
              </div>

              <details style={{ marginTop: 14 }}>
                <summary>View extracted text and chunks</summary>

                <div style={{ marginTop: 12 }}>
                  <div className="card-subtitle">Extracted text</div>
                  <pre className="code-preview" style={{ maxHeight: 220 }}>
                    {detail?.extracted_text?.slice(0, 3000) || 'Loading...'}
                  </pre>
                </div>

                <div style={{ marginTop: 12 }}>
                  <div className="card-subtitle">Chunks</div>

                  {chunks.slice(0, 5).map((chunk) => (
                    <div className="chunk-item" key={chunk.chunk_index}>
                      <div className="chunk-meta">
                        Chunk {chunk.chunk_index} · Page {chunk.page_number}
                      </div>
                      <div className="chunk-text">{chunk.chunk_text}</div>
                    </div>
                  ))}
                </div>
              </details>
            </>
          )}
        </div>
      </div>
    </>
  )
}