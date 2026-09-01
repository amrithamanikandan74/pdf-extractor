/**
 * Backend API client.
 *
 * Configuration
 * -------------
 * Set VITE_API_URL in a `.env` or `.env.local` file (or the docker-compose
 * environment) to override the default API base URL.
 *
 * Set VITE_API_KEY to the same value as API_KEY on the backend so that every
 * request includes the required X-API-Key header.
 *
 * Example .env.local:
 *   VITE_API_URL=http://localhost:8000
 *   VITE_API_KEY=dev-key
 */

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')
const API_KEY  = import.meta.env.VITE_API_KEY || 'dev-key'

/** Shared headers sent with every request. */
const AUTH_HEADERS = {
  'X-API-Key': API_KEY,
}

async function read(res) {
  let data = null
  try { data = await res.json() } catch { data = null }
  if (!res.ok) throw new Error(data?.detail || data?.message || 'Request failed')
  return data
}

export async function getStatus() {
  try {
    const res = await fetch(`${API_BASE}/status`, { headers: AUTH_HEADERS })
    if (res.ok) return res.json()
  } catch {}
  try {
    const res = await fetch(`${API_BASE}/`, { headers: AUTH_HEADERS })
    if (res.ok) return res.json()
  } catch {}
  return { search_backend: 'pgvector' }
}

export async function uploadPdf(file) {
  const formData = new FormData()
  formData.append('pdf_file', file)
  return read(await fetch(`${API_BASE}/upload-pdf`, {
    method: 'POST',
    headers: AUTH_HEADERS,
    body: formData,
  }))
}

export async function listDocuments() {
  return read(await fetch(`${API_BASE}/documents`, { headers: AUTH_HEADERS }))
}

export async function getDocument(id) {
  return read(await fetch(`${API_BASE}/documents/${id}`, { headers: AUTH_HEADERS }))
}

export async function getDocumentChunks(id) {
  return read(await fetch(`${API_BASE}/documents/${id}/chunks`, { headers: AUTH_HEADERS }))
}

export async function extractRun(documentId, schema, templateName, backend) {
  const formData = new FormData()
  const blob = new Blob([JSON.stringify(schema)], { type: 'application/json' })
  formData.append('schema_file', new File([blob], templateName || 'schema.json', { type: 'application/json' }))
  formData.append('backend', backend)
  return read(await fetch(`${API_BASE}/extract-run/${documentId}`, {
    method: 'POST',
    headers: AUTH_HEADERS,
    body: formData,
  }))
}

export async function listRuns() {
  return read(await fetch(`${API_BASE}/runs`, { headers: AUTH_HEADERS }))
}

export async function compareRuns(a, b) {
  return read(await fetch(`${API_BASE}/compare-runs/${a}/${b}`, { headers: AUTH_HEADERS }))
}

export async function searchDocument(documentId, query) {
  const url = new URL(`${API_BASE}/search/${documentId}`)
  url.searchParams.set('query', query)
  return read(await fetch(url, { method: 'POST', headers: AUTH_HEADERS }))
}