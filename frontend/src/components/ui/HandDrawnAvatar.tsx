interface HandDrawnAvatarProps {
  /** 头像显示的 emoji 或文字 */
  content: string
  /** 渐变色方案 */
  color?: 'red' | 'blue' | 'green' | 'yellow' | 'purple' | 'gold' | 'pink' | 'cyan'
  size?: 'sm' | 'md' | 'lg' | 'xl'
  /** 是否显示皇冠（用户头像） */
  crown?: boolean
  /** 在线状态 */
  status?: 'online' | 'busy' | 'offline'
  className?: string
}

const gradients: Record<string, string> = {
  red: 'from-red-400 to-orange-400',
  blue: 'from-blue-400 to-cyan-400',
  green: 'from-green-400 to-emerald-400',
  yellow: 'from-yellow-400 to-amber-400',
  purple: 'from-purple-400 to-pink-400',
  gold: 'from-yellow-300 to-orange-400',
  pink: 'from-pink-400 to-rose-400',
  cyan: 'from-cyan-400 to-blue-400',
}

const sizes = {
  sm: 'w-8 h-8 text-sm',
  md: 'w-10 h-10 text-lg',
  lg: 'w-14 h-14 text-2xl',
  xl: 'w-20 h-20 text-4xl',
}

/**
 * 手绘风格头像
 * - 圆形渐变背景 + 手绘边框
 * - 可选皇冠标识（主持人）
 * - 可选在线状态点
 */
export default function HandDrawnAvatar({
  content,
  color = 'blue',
  size = 'md',
  crown = false,
  status,
  className = '',
}: HandDrawnAvatarProps) {
  const statusColors = {
    online: 'bg-marker-green',
    busy: 'bg-marker-red',
    offline: 'bg-gray-400',
  }

  return (
    <div className={`relative inline-flex ${className}`}>
      <div
        className={`
          ${sizes[size]}
          rounded-full
          bg-gradient-to-br ${gradients[color]}
          border-2 border-ink-300 hd-filter
          flex items-center justify-center
          shadow-md
        `}
      >
        <span className="drop-shadow-sm">{content}</span>
      </div>

      {/* 皇冠 */}
      {crown && (
        <span
          className={`
            absolute -top-3 left-1/2 -translate-x-1/2
            ${size === 'sm' ? 'text-sm' : size === 'md' ? 'text-base' : size === 'lg' ? 'text-xl' : 'text-2xl'}
            drop-shadow-md
            animate-float
          `}
        >
          👑
        </span>
      )}

      {/* 状态点 */}
      {status && (
        <span
          className={`
            absolute bottom-0 right-0
            ${size === 'sm' ? 'w-2.5 h-2.5 border-2' : size === 'md' ? 'w-3 h-3 border-2' : 'w-4 h-4 border-2'}
            ${statusColors[status]}
            rounded-full
            border-paper-100
          `}
        />
      )}
    </div>
  )
}
