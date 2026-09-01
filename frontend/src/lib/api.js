const API_BASE = 'http://127.0.0.1:8000'

async function read(res) {
  let data = null
  try { data = await res.json() } catch { data = null }
  if (!res.ok) throw new Error(data?.detail || data?.message || 'Request failed')
  return data
}

export async function getStatus() {
  try {
    const res = await fetch(`${API_BASE}/status`)
    if (res.ok) return res.json()
  } catch {}
  try {
    const res = await fetch(`${API_BASE}/`)
    if (res.ok) return res.json()
  } catch {}
  return { search_backend: 'pgvector' }
}

export async function uploadPdf(file) {
  const formData = new FormData()
  formData.append('pdf_file', file)
  return read(await fetch(`${API_BASE}/upload-pdf`, { method: 'POST', body: formData }))
}

export async function listDocuments() {
  return read(await fetch(`${API_BASE}/documents`))
}

export async function getDocument(id) {
  return read(await fetch(`${API_BASE}/documents/${id}`))
}

export async function getDocumentChunks(id) {
  return read(await fetch(`${API_BASE}/documents/${id}/chunks`))
}

export async function extractRun(documentId, schema, templateName, backend) {
  const formData = new FormData()
  const blob = new Blob([JSON.stringify(schema)], { type: 'application/json' })
  formData.append('schema_file', new File([blob], templateName || 'schema.json', { type: 'application/json' }))
  formData.append('backend', backend)
  return read(await fetch(`${API_BASE}/extract-run/${documentId}`, { method: 'POST', body: formData }))
}

export async function listRuns() {
  return read(await fetch(`${API_BASE}/runs`))
}

export async function compareRuns(a, b) {
  return read(await fetch(`${API_BASE}/compare-runs/${a}/${b}`))
}

export async function searchDocument(documentId, query) {
  const url = new URL(`${API_BASE}/search/${documentId}`)
  url.searchParams.set('query', query)
  return read(await fetch(url, { method: 'POST' }))
}