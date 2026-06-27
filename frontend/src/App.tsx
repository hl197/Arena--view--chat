import { Routes, Route, useLocation } from 'react-router-dom'
import Header from './components/layout/Header'
import HomePage from './pages/HomePage'
import DebatePage from './pages/DebatePage'
import ResultPage from './pages/ResultPage'
import HistoryPage from './pages/HistoryPage'
import SettingsPage from './pages/SettingsPage'

/** 标准页面布局（Header + 深色背景） */
function StandardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Header />
      <main className="max-w-7xl mx-auto px-4 py-8">
        {children}
      </main>
    </div>
  )
}

export default function App() {
  const location = useLocation()
  const isChatPage = location.pathname.startsWith('/debate/')

  // 群聊页面——全屏独立布局（微信风格）
  if (isChatPage) {
    return (
      <Routes>
        <Route path="/debate/:sessionId" element={<DebatePage />} />
      </Routes>
    )
  }

  // 其他页面——标准布局
  return (
    <StandardLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/result/:sessionId" element={<ResultPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </StandardLayout>
  )
}
