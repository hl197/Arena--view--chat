import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Header from './components/layout/Header'
import HomePage from './pages/HomePage'
import DebatePage from './pages/DebatePage'
import SettingsPage from './pages/SettingsPage'
import MePage from './pages/MePage'
import AuthPage from './pages/AuthPage'
import { useAuthStore } from './store/authStore'

/**
 * 标准页面布局（手绘手账风 + Header）
 * 用于：首页、设置页
 */
function StandardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-paper-100 text-ink-300">
      <Header />
      <main className="max-w-6xl mx-auto">{children}</main>
    </div>
  )
}

export default function App() {
  const location = useLocation()
  const isChatPage = location.pathname.startsWith('/debate')
  const loadFromStorage = useAuthStore((s) => s.loadFromStorage)

  // 应用启动时从 localStorage 恢复认证状态
  useEffect(() => {
    loadFromStorage()
  }, [loadFromStorage])

  // 群聊页面——两栏式独立布局（带或不带 sessionId）
  if (isChatPage) {
    return (
      <Routes>
        <Route path="/debate/:sessionId" element={<DebatePage />} />
        <Route path="/debate" element={<DebatePage />} />
      </Routes>
    )
  }

  // 其他页面——标准布局
  return (
    <StandardLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/me" element={<MePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/auth" element={<AuthPage />} />
      </Routes>
    </StandardLayout>
  )
}
