/** 认证页 — 登录 / 注册 · 手绘手账风 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import HandDrawnCard from '../components/ui/HandDrawnCard'
import HandDrawnButton from '../components/ui/HandDrawnButton'
import { HandDrawnInput } from '../components/ui/HandDrawnInput'
import HandDrawnDivider from '../components/ui/HandDrawnDivider'

type Tab = 'login' | 'register'

export default function AuthPage() {
  const navigate = useNavigate()
  const { login, register } = useAuthStore()
  const [tab, setTab] = useState<Tab>('login')

  // 表单字段
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')

  // 状态
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  /** 切换 Tab 时清空表单和错误 */
  const switchTab = (t: Tab) => {
    setTab(t)
    setError('')
    setSuccess('')
    setEmail('')
    setPassword('')
    setConfirmPassword('')
  }

  /** 客户端校验 */
  const validate = (): string | null => {
    if (!email.trim()) return '请输入邮箱'
    if (!email.includes('@') || !email.includes('.')) return '请输入有效的邮箱地址'
    if (!password) return '请输入密码'
    if (tab === 'register') {
      if (password.length < 8) return '密码至少需要 8 个字符'
      if (password !== confirmPassword) return '两次输入的密码不一致'
    }
    return null
  }

  /** 提交 */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    const validationError = validate()
    if (validationError) {
      setError(validationError)
      return
    }

    setLoading(true)
    try {
      if (tab === 'login') {
        await login(email.trim(), password)
        setSuccess('登录成功，即将跳转...')
      } else {
        await register(email.trim(), password)
        setSuccess('注册成功，即将跳转...')
      }
      // 延迟跳转，让用户看到成功提示
      setTimeout(() => navigate('/'), 800)
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen paper-bg">
      <div className="max-w-md mx-auto pt-16 pb-12 px-4">
        {/* 标题 */}
        <div className="text-center mb-8">
          <span className="text-4xl mb-3 block">📓</span>
          <h1 className="text-2xl font-bold text-ink-300 font-hand">
            {tab === 'login' ? '欢迎回来' : '加入 ArenaView'}
          </h1>
          <p className="text-ink-50 text-sm mt-1">
            {tab === 'login' ? '登录以查看你的决策分析历史' : '注册账号，保存你的决策分析记录'}
          </p>
        </div>

        {/* Tab 切换 */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => switchTab('login')}
            className={`flex-1 py-2.5 rounded-hd-md border-2 text-sm font-medium transition-all hd-filter ${
              tab === 'login'
                ? 'border-marker-blue bg-marker-blue/10 text-marker-blue'
                : 'border-divider text-ink-50 hover:border-marker-blue/30 hover:text-ink-100'
            }`}
          >
            登录
          </button>
          <button
            onClick={() => switchTab('register')}
            className={`flex-1 py-2.5 rounded-hd-md border-2 text-sm font-medium transition-all hd-filter ${
              tab === 'register'
                ? 'border-marker-blue bg-marker-blue/10 text-marker-blue'
                : 'border-divider text-ink-50 hover:border-marker-blue/30 hover:text-ink-100'
            }`}
          >
            注册
          </button>
        </div>

        {/* 表单卡片 */}
        <HandDrawnCard variant="white" className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <HandDrawnInput
              label="邮箱"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your@email.com"
              variant="filled"
              autoComplete="email"
            />

            <HandDrawnInput
              label="密码"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={tab === 'register' ? '至少 8 个字符' : '输入密码'}
              variant="filled"
              autoComplete={tab === 'register' ? 'new-password' : 'current-password'}
            />

            {tab === 'register' && (
              <HandDrawnInput
                label="确认密码"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="再次输入密码"
                variant="filled"
                autoComplete="new-password"
              />
            )}

            {/* 错误提示 */}
            {error && (
              <div className="bg-marker-red/10 border-2 border-marker-red/40 rounded-hd-md p-3 text-marker-red text-sm hd-filter">
                ⚠️ {error}
              </div>
            )}

            {/* 成功提示 */}
            {success && (
              <div className="bg-marker-green/15 border-2 border-marker-green/40 rounded-hd-md p-3 text-marker-green text-sm hd-filter">
                ✅ {success}
              </div>
            )}

            {/* 提交按钮 */}
            <HandDrawnButton
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              tilt="right"
              disabled={loading}
            >
              {loading
                ? '处理中...'
                : tab === 'login'
                  ? '🔑 登录'
                  : '✨ 注册'}
            </HandDrawnButton>
          </form>

          <HandDrawnDivider variant="dashed" className="my-4" />

          {/* 底部切换提示 */}
          <p className="text-center text-xs text-ink-50">
            {tab === 'login' ? (
              <>
                还没有账号？{' '}
                <button
                  onClick={() => switchTab('register')}
                  className="text-marker-blue hover:underline font-medium"
                >
                  立即注册
                </button>
              </>
            ) : (
              <>
                已有账号？{' '}
                <button
                  onClick={() => switchTab('login')}
                  className="text-marker-blue hover:underline font-medium"
                >
                  去登录
                </button>
              </>
            )}
          </p>
        </HandDrawnCard>

        {/* 底部装饰 */}
        <p className="text-center mt-8 text-ink-50 text-xs opacity-50">
          ✨ 你的每一个决策，都值得被认真对待
        </p>
      </div>
    </div>
  )
}
