import { useState } from 'react'
import HandDrawnAvatar from '../ui/HandDrawnAvatar'
import HandDrawnBadge from '../ui/HandDrawnBadge'

interface HistoryCardProps {
  sessionId: string
  title: string
  status: 'completed' | 'processing' | 'error'
  perspectivesCount: number
  timeLabel: string
  active?: boolean
  onClick?: () => void
  onDelete?: () => void
}

const AVATAR_COLORS = ['red', 'blue', 'green', 'purple', 'gold', 'pink', 'cyan'] as const

export default function HistoryCard({
  sessionId,
  title,
  status,
  perspectivesCount,
  timeLabel,
  active = false,
  onClick,
  onDelete,
}: HistoryCardProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const statusMap = {
    completed: { variant: 'success' as const, dot: true, label: '已完成' },
    processing: { variant: 'warning' as const, dot: true, label: '进行中' },
    error: { variant: 'danger' as const, dot: false, label: '出错' },
  }

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!showDeleteConfirm) {
      setShowDeleteConfirm(true)
      return
    }
    onDelete?.()
    setShowDeleteConfirm(false)
  }

  // 根据 sessionId 选一个头像颜色（伪随机但稳定）
  const colorIdx = sessionId.charCodeAt(0) % AVATAR_COLORS.length
  const avatarColor = AVATAR_COLORS[colorIdx]
  const avatarEmoji = ['📊', '🧠', '💼', '⚖️', '🎯', '💡', '📚'][colorIdx]

  return (
    <div
      onClick={onClick}
      className={`
        relative p-3 rounded-hd-md border-2 hd-filter cursor-pointer
        transition-all duration-200
        ${active
          ? 'bg-sticky-cream border-marker-gold shadow-sticky-hover scale-[1.02]'
          : 'bg-sticky-white border-divider hover:border-marker-blue/60 hover:shadow-sticky-hover hover:scale-[1.01] hover:-rotate-0'
        }
        group
      `}
      style={{ transform: active ? undefined : `rotate(${Math.sin(sessionId.length) * 0.5}deg)` }}
    >
      {/* 纸胶带装饰 */}
      <div className={`absolute -top-1.5 left-1/2 -translate-x-1/2 w-10 h-2.5 rounded-sm pointer-events-none ${
        active ? 'bg-marker-gold/40' : 'bg-washi-pink/40'
      }`} />

      {/* 删除按钮 */}
      <button
        onClick={handleDeleteClick}
        className={`
          absolute -top-2 -right-2 w-6 h-6 rounded-full
          flex items-center justify-center text-xs
          transition-all duration-200 z-10
          ${showDeleteConfirm
            ? 'bg-marker-red text-white opacity-100 scale-110'
            : 'bg-marker-red/80 text-white opacity-0 group-hover:opacity-100'
          }
        `}
        title={showDeleteConfirm ? '再次点击确认删除' : '删除'}
      >
        {showDeleteConfirm ? '✓' : '🗑️'}
      </button>

      <div className="flex items-start gap-2.5">
        <HandDrawnAvatar content={avatarEmoji} color={avatarColor} size="sm" />

        <div className="flex-1 min-w-0">
          <p className="text-sm text-ink-300 font-medium leading-snug line-clamp-2 mb-1.5">
            {title}
          </p>
          <div className="flex items-center justify-between text-xs">
            <HandDrawnBadge variant={statusMap[status].variant} dot={statusMap[status].dot} size="sm">
              {statusMap[status].label}
            </HandDrawnBadge>
            <span className="text-ink-50 flex items-center gap-1">
              <span>👥 {perspectivesCount}</span>
            </span>
          </div>
          <p className="text-[10px] text-ink-50 mt-1 text-right">{timeLabel}</p>
        </div>
      </div>
    </div>
  )
}
