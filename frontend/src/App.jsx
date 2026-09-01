import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import UsersPage from './pages/UsersPage.jsx'
import PdfsPage from './pages/PdfsPage.jsx'
import TemplatesPage from './pages/TemplatesPage.jsx'
import ExtractionPage from './pages/ExtractionPage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import ComparePage from './pages/ComparePage.jsx'
import ChatbotPage from './pages/ChatbotPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/pdfs" element={<PdfsPage />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/extract" element={<ExtractionPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/chatbot" element={<ChatbotPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}