import { NavLink, Outlet, useLocation } from 'react-router-dom'

const nav = [
  { to: '/', label: 'Dashboard', exact: true },
  { to: '/users', label: '1. Add User' },
  { to: '/pdfs', label: '2. Upload PDF' },
  { to: '/templates', label: '3. Upload Template' },
  { to: '/extract', label: '4. Run Extraction' },
  { to: '/history', label: '5. View History' },
  { to: '/compare', label: '6. Compare Results' },
  { to: '/chatbot', label: '7. Ask PDF' },
]

const pageNames = {
  '/': 'Dashboard',
  '/users': 'Add User',
  '/pdfs': 'Upload PDF',
  '/templates': 'Upload Template',
  '/extract': 'Run Extraction',
  '/history': 'View History',
  '/compare': 'Compare Results',
  '/chatbot': 'Ask PDF',
}

export default function Layout() {
  const location = useLocation()
  const currentPage = pageNames[location.pathname] || 'Page'

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="brand">
            <div>
              <div className="brand-name">DocuExtract</div>
              <div className="brand-sub">AI Platform</div>
            </div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.exact}
              className={({ isActive }) =>
                isActive ? 'nav-item active' : 'nav-item'
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <div className="topbar-breadcrumb">
              DocuExtract
              <span>{currentPage}</span>
            </div>
          </div>
        </header>

        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}