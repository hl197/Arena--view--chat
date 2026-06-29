import { ReactNode } from 'react'

interface HandDrawnBadgeProps {
  children: ReactNode
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'gold'
  size?: 'sm' | 'md'
  dot?: boolean
  className?: string
}

/**
 * 手绘风格徽章 / 标签
 * - 圆角矩形 + 手绘边框 + 马克笔填充色
 * - 可选小圆点模式
 */
export default function HandDrawnBadge({
  children,
  variant = 'default',
  size = 'sm',
  dot = false,
  className = '',
}: HandDrawnBadgeProps) {
  const variants = {
    default: 'bg-paper-200 text-ink-200 border-divider',
    success: 'bg-marker-green/15 text-marker-green border-marker-green/40',
    warning: 'bg-marker-yellow/20 text-amber-700 border-marker-yellow/50',
    danger: 'bg-marker-red/15 text-marker-red border-marker-red/40',
    info: 'bg-marker-blue/15 text-marker-blue border-marker-blue/40',
    gold: 'bg-marker-gold/20 text-amber-700 border-marker-gold/50',
  }

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
  }

  const dotColors = {
    default: 'bg-ink-200',
    success: 'bg-marker-green',
    warning: 'bg-marker-yellow',
    danger: 'bg-marker-red',
    info: 'bg-marker-blue',
    gold: 'bg-marker-gold',
  }

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 rounded-full border-2 hd-filter font-medium
        ${variants[variant]}
        ${sizes[size]}
        ${className}
      `}
    >
      {dot && (
        <span className={`w-1.5 h-1.5 rounded-full ${dotColors[variant]} ${variant === 'success' ? 'animate-pulse' : ''}`} />
      )}
      {children}
    </span>
  )
}
