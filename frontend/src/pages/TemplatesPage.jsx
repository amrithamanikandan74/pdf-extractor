import { useEffect, useRef, useState } from 'react'
import { addTemplate, deleteTemplate, loadWorkspace, updateTemplate } from '../lib/store'

const SAMPLE = `{
  "schema_name": "invoice_extraction",
  "fields": {
    "invoice_number": { "type": "string", "description": "Invoice number or ID" },
    "vendor_name": { "type": "string", "description": "Company issuing the invoice" },
    "invoice_date": { "type": "string", "description": "Date of the invoice" },
    "due_date": { "type": "string", "description": "Payment due date" },
    "total_amount": { "type": "number", "description": "Final total amount including tax" },
    "tax_amount": { "type": "number", "description": "Tax amount applied" }
  }
}`

export default function TemplatesPage() {
  const fileRef = useRef(null)
  const [ws, setWs] = useState(loadWorkspace())
  const [edit, setEdit] = useState(null)
  const [err, setErr] = useState('')
  const [success, setSuccess] = useState('')
  const [form, setForm] = useState({
    name: '',
    description: '',
    schemaText: '',
  })

  useEffect(() => {
    const refresh = () => setWs(loadWorkspace())
    window.addEventListener('workspace-updated', refresh)
    return () => window.removeEventListener('workspace-updated', refresh)
  }, [])

  function save(e) {
    e.preventDefault()
    setErr('')
    setSuccess('')

    try {
      const schema = JSON.parse(form.schemaText)

      const data = {
        name: form.name || schema.schema_name || 'Untitled template',
        description: form.description,
        schema,
      }

      edit ? updateTemplate(edit, data) : addTemplate(data)

      setEdit(null)
      setForm({ name: '', description: '', schemaText: '' })
      setSuccess(edit ? 'Template updated.' : 'Template created.')
    } catch {
      setErr('Invalid JSON. Check your syntax — commas, brackets and quotes.')
    }
  }

  function start(template) {
    setEdit(template.id)
    setForm({
      name: template.name,
      description: template.description || '',
      schemaText: JSON.stringify(template.schema, null, 2),
    })
    setErr('')
    setSuccess('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function upload(file) {
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.json')) {
      setErr('Please upload a JSON file only.')
      setSuccess('')
      return
    }

    try {
      const text = await file.text()
      const schema = JSON.parse(text)

      setForm({
        name: schema.schema_name || file.name.replace(/\.json$/i, ''),
        description: 'Uploaded JSON template',
        schemaText: JSON.stringify(schema, null, 2),
      })

      setEdit(null)
      setErr('')
      setSuccess('JSON loaded. You can edit it and click Create Template.')

      if (fileRef.current) fileRef.current.value = ''
    } catch {
      setErr('Invalid JSON file. Please check the JSON format.')
      setSuccess('')
    }
  }

  function fieldCount(template) {
    return Object.keys(template.schema?.fields || {}).length
  }

  function cancelEdit() {
    setEdit(null)
    setForm({ name: '', description: '', schemaText: '' })
    setErr('')
    setSuccess('')
  }

  return (
    <>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Templates</h1>
          <p>Define JSON schemas that tell the AI exactly what fields to extract from your PDFs.</p>
        </div>

        <div className="page-header-actions">
          <span className="badge neutral">{ws.templates.length} templates</span>
        </div>
      </div>

      {err && <div className="alert error">{err}</div>}
      {success && <div className="alert success">{success}</div>}

      <div className="grid-2" style={{ alignItems: 'start' }}>
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">{edit ? 'Edit Template' : 'New Template'}</div>
              <div className="card-subtitle">
                {edit ? 'Modify schema and metadata' : 'Create or upload a JSON template'}
              </div>
            </div>

            {edit && (
              <button className="btn sm" onClick={cancelEdit}>
                Cancel
              </button>
            )}
          </div>

          <form onSubmit={save}>
            <div className="form-group">
              <label>Template name</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Invoice Extraction"
              />
            </div>

            <div className="form-group">
              <label>Description</label>
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Fields to extract from invoices"
              />
            </div>

            <div className="form-group">
              <label>JSON Schema</label>
              <textarea
                className="code"
                value={form.schemaText}
                onChange={(e) => setForm({ ...form, schemaText: e.target.value })}
                placeholder={SAMPLE}
                style={{ minHeight: 240 }}
              />
            </div>

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="submit" className="btn primary">
                {edit ? 'Save Changes' : 'Save Template'}
              </button>

              <button
                type="button"
                className="btn"
                onClick={() => fileRef.current.click()}
              >
                Upload JSON
              </button>

              <button
                type="button"
                className="btn"
                onClick={() =>
                  setForm({
                    name: 'Invoice Extraction',
                    description: 'Sample invoice extraction template',
                    schemaText: SAMPLE,
                  })
                }
              >
                Load Sample
              </button>

              <input
                ref={fileRef}
                type="file"
                accept=".json,application/json"
                hidden
                onChange={(e) => upload(e.target.files[0])}
              />
            </div>
          </form>
        </div>

        <div className="card">
          <div className="card-header">
            <div className="card-title">Saved Templates</div>
          </div>

          {ws.templates.length === 0 ? (
            <div className="empty-state">
              <p>No templates yet. Upload or create one on the left.</p>
            </div>
          ) : (
            ws.templates.map((template) => (
              <div key={template.id} className="record-row">
                <div className="record-row-left">
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 8,
                      background: 'var(--accent-2-light)',
                      flexShrink: 0,
                    }}
                  />

                  <div style={{ minWidth: 0 }}>
                    <div
                      className="record-row-name"
                      style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                    >
                      <span
                        className="truncate"
                        style={{ maxWidth: 160, display: 'block' }}
                      >
                        {template.name}
                      </span>
                      <span className="badge neutral">{fieldCount(template)} fields</span>
                    </div>

                    <div className="record-row-sub">
                      {template.description || 'No description'}
                    </div>
                  </div>
                </div>

                <div className="record-row-actions">
                  <button className="btn sm" onClick={() => start(template)}>
                    Edit
                  </button>

                  <button
                    className="btn sm danger"
                    onClick={() => deleteTemplate(template.id)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  )
}