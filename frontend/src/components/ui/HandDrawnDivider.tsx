interface HandDrawnDividerProps {
  variant?: 'line' | 'washi' | 'dashed' | 'doodle'
  color?: 'default' | 'pink' | 'blue' | 'yellow'
  label?: string
  className?: string
}

/**
 * 手绘风格分割线
 * - 多种样式：直线 / 纸胶带 / 虚线 / 涂鸦波浪线
 */
export default function HandDrawnDivider({
  variant = 'line',
  color = 'default',
  label,
  className = '',
}: HandDrawnDividerProps) {
  const colors = {
    default: 'bg-divider',
    pink: 'bg-washi-pink/60',
    blue: 'bg-washi-blue/60',
    yellow: 'bg-washi-yellow/60',
  }

  if (label) {
    return (
      <div className={`flex items-center gap-3 my-4 ${className}`}>
        <div className="flex-1 h-px hd-filter bg-divider" />
        <span className="text-xs text-ink-50 font-medium px-2">{label}</span>
        <div className="flex-1 h-px hd-filter bg-divider" />
      </div>
    )
  }

  if (variant === 'washi') {
    return (
      <div className={`relative h-3 my-3 ${className}`}>
        <div className={`absolute inset-0 ${colors[color]} rounded-sm hd-filter transform -rotate-1`} />
      </div>
    )
  }

  if (variant === 'dashed') {
    return (
      <div className={`my-3 ${className}`}>
        <div className="h-0.5 border-t-2 border-dashed border-divider hd-filter" />
      </div>
    )
  }

  if (variant === 'doodle') {
    return (
      <div className={`my-4 ${className}`}>
        <svg className="w-full h-4 hd-filter" viewBox="0 0 200 16" preserveAspectRatio="none">
          <path
            d="M0,8 Q25,2 50,8 T100,8 T150,8 T200,8"
            stroke="#d4cfc7"
            strokeWidth="2"
            fill="none"
            strokeLinecap="round"
          />
        </svg>
      </div>
    )
  }

  // line (default)
  return (
    <div className={`my-3 ${className}`}>
      <div className="h-0.5 bg-divider hd-filter" />
    </div>
  )
}
