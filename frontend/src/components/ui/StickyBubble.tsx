import { ReactNode } from 'react'

interface StickyBubbleProps {
  children: ReactNode
  variant?: 'white' | 'cream' | 'blue' | 'pink' | 'green' | 'gold'
  side?: 'left' | 'right'
  senderName?: string
  timestamp?: string
  tapeColor?: 'pink' | 'blue' | 'yellow' | 'green' | 'purple'
  className?: string
}

/**
 * 便利贴消息气泡
 * - 微微倾斜（左/右对应发话方向）
 * - 顶部纸胶带装饰
 * - 柔和阴影，像贴在纸上
 */
export default function StickyBubble({
  children,
  variant = 'white',
  side = 'left',
  senderName,
  timestamp,
  tapeColor = 'pink',
  className = '',
}: StickyBubbleProps) {
  const variants = {
    white: 'bg-sticky-white border-divider text-ink-300',
    cream: 'bg-sticky-cream border-marker-gold/60 text-ink-300',
    blue: 'bg-sticky-blue border-marker-blue/50 text-ink-300',
    pink: 'bg-sticky-pink border-marker-red/40 text-ink-300',
    green: 'bg-sticky-green border-marker-green/50 text-ink-300',
    gold: 'bg-sticky-cream border-marker-gold text-ink-300 shadow-[0_0_16px_rgba(212,168,67,0.25)]',
  }

  const tapeColors = {
    pink: 'bg-washi-pink/50',
    blue: 'bg-washi-blue/50',
    yellow: 'bg-washi-yellow/50',
    green: 'bg-washi-green/50',
    purple: 'bg-marker-purple/30',
  }

  const tilt = side === 'left' ? 'rotate-[-0.6deg]' : 'rotate-[0.5deg]'
  const tapeAlign = side === 'left' ? 'left-4' : 'right-4'

  return (
    <div className={`max-w-[70%] ${side === 'right' ? 'ml-auto' : 'mr-auto'}`}>
      {senderName && (
        <p className={`text-xs font-semibold text-ink-50 mb-1.5 ${side === 'right' ? 'text-right' : 'text-left'}`}>
          {senderName}
        </p>
      )}
      <div
        className={`
          relative rounded-hd-lg border-2 hd-filter
          px-4 py-3 shadow-sticky
          ${variants[variant]}
          ${tilt}
          ${className}
        `}
      >
        {/* 纸胶带 */}
        <div className={`absolute -top-2 ${tapeAlign} w-10 h-3 ${tapeColors[tapeColor]} rounded-sm pointer-events-none`} />

        {/* 消息内容 */}
        <div className="text-sm leading-relaxed">
          {children}
        </div>

        {timestamp && (
          <p className="text-[10px] text-ink-50 mt-1 text-right opacity-60">
            {timestamp}
          </p>
        )}
      </div>
    </div>
  )
}
