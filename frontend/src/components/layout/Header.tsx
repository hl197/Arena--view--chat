import { Link, useNavigate } from 'react-router-dom'
import { useUserStore, getUserAvatar } from '../../store/userStore'
import { useAuthStore } from '../../store/authStore'
import HandDrawnAvatar from '../ui/HandDrawnAvatar'

export default function Header() {
  const navigate = useNavigate()
  const gender = useUserStore((s) => s.gender)
  const { isLoggedIn, user, logout } = useAuthStore()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <header className="border-b-2 border-divider bg-paper-100/80 backdrop-blur hd-filter">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 text-xl font-bold text-ink-300">
          <span className="text-marker-purple">📓</span>
          <span className="font-hand tracking-wider">ArenaView</span>
        </Link>
        <nav className="flex items-center gap-4 text-sm text-ink-100">
          <Link
            to="/settings"
            className="px-3 py-1.5 rounded-hd-md border-2 border-transparent hover:border-divider hover:bg-paper-200 transition-all hd-filter"
          >
            <span className="mr-1.5">⚙️</span>
            API 设置
          </Link>
          <Link
            to="/me"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-hd-md border-2 border-transparent hover:border-divider hover:bg-paper-200 transition-all hd-filter"
          >
            <HandDrawnAvatar
              src={getUserAvatar(gender)}
              content="😊"
              color={gender === 'male' ? 'blue' : 'pink'}
              size="sm"
            />
            <span>我的</span>
          </Link>

          {/* 认证状态 */}
          {isLoggedIn ? (
            <div className="flex items-center gap-3">
              <span className="text-xs text-ink-100 max-w-[120px] truncate" title={user?.email}>
                {user?.email ?? ''}
              </span>
              <button
                onClick={handleLogout}
                className="px-3 py-1.5 rounded-hd-md border-2 border-marker-red/30 text-marker-red hover:bg-marker-red/5 transition-all hd-filter text-xs"
              >
                退出
              </button>
            </div>
          ) : (
            <Link
              to="/auth"
              className="px-3 py-1.5 rounded-hd-md border-2 border-marker-blue/30 text-marker-blue hover:bg-marker-blue/5 transition-all hd-filter"
            >
              登录
            </Link>
          )}
        </nav>
      </div>
    </header>
  )
}
