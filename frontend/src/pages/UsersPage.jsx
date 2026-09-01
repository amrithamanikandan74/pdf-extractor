import { useEffect, useState } from 'react'
import { addUser, deleteUser, loadWorkspace, updateUser } from '../lib/store'

function initials(name) {
  return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
}

const COLORS = [
  { bg: '#edf0fe', color: '#4f6ef7' },
  { bg: '#ecfdf5', color: '#059669' },
  { bg: '#fffbeb', color: '#d97706' },
  { bg: '#fef2f2', color: '#ef4444' },
  { bg: '#f5f3ff', color: '#7c3aed' },
]

export default function UsersPage() {
  const [ws, setWs] = useState(loadWorkspace())
  const [form, setForm] = useState({ name: '', purpose: '', email: '' })
  const [editing, setEditing] = useState(null)
  const [err, setErr] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    const refresh = () => setWs(loadWorkspace())
    window.addEventListener('workspace-updated', refresh)
    return () => window.removeEventListener('workspace-updated', refresh)
  }, [])

  function submit(e) {
    e.preventDefault()
    setErr(''); setSuccess('')
    if (!form.name.trim()) { setErr('User name is required.'); return }
    const data = { name: form.name.trim(), purpose: form.purpose, email: form.email }
    if (editing) {
      updateUser(editing, data)
      setSuccess('User updated successfully.')
    } else {
      addUser(data)
      setSuccess('User created successfully.')
    }
    setForm({ name: '', purpose: '', email: '' })
    setEditing(null)
  }

  function edit(u) {
    setEditing(u.id)
    setForm({ name: u.name, purpose: u.purpose || '', email: u.email || '' })
    setErr(''); setSuccess('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function cancel() {
    setEditing(null)
    setForm({ name: '', purpose: '', email: '' })
    setErr(''); setSuccess('')
  }

  return (
    <>
      <div className="page-header">
        <div className="page-header-left">
          <h1>Users</h1>
          <p>Manage user accounts and track who runs each extraction.</p>
        </div>
        <div className="page-header-actions">
          <span className="badge neutral">{ws.users.length} total</span>
        </div>
      </div>

      {err && <div className="alert error">{err}</div>}
      {success && <div className="alert success">{success}</div>}

      <div className="grid-2" style={{alignItems:'start'}}>
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">{editing ? 'Edit User' : 'Add New User'}</div>
              <div className="card-subtitle">{editing ? 'Update user information' : 'Create a user to tag extractions'}</div>
            </div>
          </div>

          <form onSubmit={submit}>
            <div className="form-group">
              <label>Full name *</label>
              <input
                value={form.name}
                onChange={e => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Sarah Connor"
              />
            </div>

            <div className="form-group">
              <label>Email address</label>
              <input
                type="email"
                value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}
                placeholder="e.g. sarah@company.com"
              />
            </div>

            <div className="form-group">
              <label>Role / Purpose</label>
              <input
                value={form.purpose}
                onChange={e => setForm({ ...form, purpose: e.target.value })}
                placeholder="e.g. Finance analyst, Compliance officer"
              />
            </div>

            <div style={{display:'flex', gap:8, marginTop:6}}>
              <button type="submit" className="btn primary full">
                {editing ? 'Update User' : 'Create User'}
              </button>
              {editing && (
                <button type="button" className="btn" onClick={cancel}>Cancel</button>
              )}
            </div>
          </form>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">All Users</div>
              <div className="card-subtitle">{ws.users.length} registered</div>
            </div>
          </div>

          {ws.users.length === 0 ? (
            <div className="empty-state">
              <svg viewBox="0 0 20 20" fill="currentColor"><path d="M9 6a3 3 0 11-6 0 3 3 0 016 0zM17 6a3 3 0 11-6 0 3 3 0 016 0zM12.93 17c.046-.327.07-.66.07-1a6.97 6.97 0 00-1.5-4.33A5 5 0 0119 16v1h-6.07zM6 11a5 5 0 015 5v1H1v-1a5 5 0 015-5z"/></svg>
              <p>No users yet. Add one on the left.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th style={{width:100}}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {ws.users.map((u, i) => {
                    const c = COLORS[i % COLORS.length]
                    return (
                      <tr key={u.id} style={editing === u.id ? {background:'var(--accent-light)'} : {}}>
                        <td>
                          <div style={{display:'flex', alignItems:'center', gap:10}}>
                            <div className="avatar" style={{background:c.bg, color:c.color, width:30, height:30, fontSize:11}}>
                              {initials(u.name)}
                            </div>
                            <span style={{fontWeight:500}}>{u.name}</span>
                          </div>
                        </td>
                        <td style={{color:'var(--text-muted)', fontSize:12.5}}>
                          {u.email || <span style={{opacity:0.4}}>—</span>}
                        </td>
                        <td>
                          {u.purpose
                            ? <span className="tag">{u.purpose}</span>
                            : <span style={{color:'var(--text-muted)', fontSize:12}}>—</span>
                          }
                        </td>
                        <td>
                          <div style={{display:'flex', gap:4}}>
                            <button className="btn sm" onClick={() => edit(u)}>Edit</button>
                            <button className="btn sm danger" onClick={() => deleteUser(u.id)}>Delete</button>
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
      </div>
    </>
  )
}