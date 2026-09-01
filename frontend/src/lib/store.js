const KEY = 'pdf_extract_workspace_v3'

const defaultWorkspace = {
  users: [],
  templates: [],
  mappings: [],
  extractionMeta: {},
  hiddenPdfIds: [],
}

function uid(prefix) {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

export function loadWorkspace() {
  try {
    return { ...defaultWorkspace, ...(JSON.parse(localStorage.getItem(KEY)) || {}) }
  } catch {
    return defaultWorkspace
  }
}

export function saveWorkspace(ws) {
  localStorage.setItem(KEY, JSON.stringify(ws))
  window.dispatchEvent(new Event('workspace-updated'))
  return ws
}

export function resetWorkspace() {
  localStorage.removeItem(KEY)
  window.dispatchEvent(new Event('workspace-updated'))
}

export function addUser(data) {
  const ws = loadWorkspace()
  ws.users.unshift({ id: uid('user'), createdAt: new Date().toISOString(), ...data })
  return saveWorkspace(ws)
}
export function updateUser(id, data) {
  const ws = loadWorkspace()
  ws.users = ws.users.map(u => u.id === id ? { ...u, ...data } : u)
  return saveWorkspace(ws)
}
export function deleteUser(id) {
  const ws = loadWorkspace()
  ws.users = ws.users.filter(u => u.id !== id)
  return saveWorkspace(ws)
}

export function addTemplate(data) {
  const ws = loadWorkspace()
  ws.templates.unshift({ id: uid('tpl'), createdAt: new Date().toISOString(), ...data })
  return saveWorkspace(ws)
}
export function updateTemplate(id, data) {
  const ws = loadWorkspace()
  ws.templates = ws.templates.map(t => t.id === id ? { ...t, ...data } : t)
  return saveWorkspace(ws)
}
export function deleteTemplate(id) {
  const ws = loadWorkspace()
  ws.templates = ws.templates.filter(t => t.id !== id)
  return saveWorkspace(ws)
}

export function hidePdf(id) {
  const ws = loadWorkspace()
  if (!ws.hiddenPdfIds.includes(id)) ws.hiddenPdfIds.push(id)
  return saveWorkspace(ws)
}

export function rememberExtraction(runId, meta) {
  const ws = loadWorkspace()
  ws.extractionMeta[runId] = { ...meta, savedAt: new Date().toISOString() }
  ws.mappings.unshift({ id: uid('map'), runId, ...meta, createdAt: new Date().toISOString() })
  return saveWorkspace(ws)
}
export function deleteExtraction(runId) {
  const ws = loadWorkspace()

  ws.mappings = (ws.mappings || []).filter(item => item.runId !== runId)
  delete ws.extractionMeta[runId]

  return saveWorkspace(ws)
}