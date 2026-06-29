import { ReactNode, useState } from 'react'

interface HandDrawnCardProps {
  children: ReactNode
  variant?: 'white' | 'cream' | 'blue' | 'pink' | 'green'
  hoverable?: boolean
  tilt?: 'left' | 'right' | 'alternate' | 'none'
  active?: boolean
  className?: string
  onClick?: () => void
}

/**
 * 手绘风格卡片
 * - 便利贴造型 + 手绘边框
 * - 微微倾斜（左右交替更自然）
 * - hover 上浮 + 阴影加深
 */
export default function HandDrawnCard({
  children,
  variant = 'white',
  hoverable = false,
  tilt = 'alternate',
  active = false,
  className = '',
  onClick,
}: HandDrawnCardProps) {
  const [alternateIndex] = useState(() => Math.random() > 0.5 ? 'left' : 'right')

  const variants = {
    white: 'bg-sticky-white border-divider',
    cream: 'bg-sticky-cream border-marker-gold',
    blue: 'bg-sticky-blue border-marker-blue',
    pink: 'bg-sticky-pink border-marker-red',
    green: 'bg-sticky-green border-marker-green',
  }

  const tiltClass = tilt === 'alternate'
    ? (alternateIndex === 'left' ? 'rotate-[-0.6deg]' : 'rotate-[0.5deg]')
    : tilt === 'left'
      ? 'rotate-[-0.6deg]'
      : tilt === 'right'
        ? 'rotate-[0.5deg]'
        : ''

  return (
    <div
      className={`
        relative rounded-hd-lg border-2 hd-filter
        ${variants[variant]}
        ${tiltClass}
        ${hoverable ? 'transition-all duration-200 cursor-pointer hover:scale-[1.02] hover:rotate-0 hover:shadow-sticky-hover' : ''}
        ${active ? 'ring-2 ring-marker-gold ring-offset-2 ring-offset-paper-100 shadow-sticky-hover' : 'shadow-sticky'}
        ${className}
      `}
      onClick={onClick}
    >
      {/* 顶部纸胶带装饰 */}
      <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-12 h-3 bg-washi-pink/40 rounded-sm pointer-events-none" />
      {children}
    </div>
  )
}
