/** 消息右键菜单 — 手绘风格 */
import { useEffect, useRef } from 'react'

interface ContextMenuItem {
  icon: string
  label: string
  onClick: () => void
  danger?: boolean
  divider?: boolean
}

interface MessageContextMenuProps {
  x: number
  y: number
  items: ContextMenuItem[]
  onClose: () => void
}

export default function MessageContextMenu({ x, y, items, onClose }: MessageContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleEsc)
    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleEsc)
    }
  }, [onClose])

  // 计算菜单位置，避免超出视口
  const menuWidth = 140
  const menuHeight = items.length * 36 + 8
  const adjustedX = x + menuWidth > window.innerWidth ? x - menuWidth : x
  const adjustedY = y + menuHeight > window.innerHeight ? y - menuHeight : y

  return (
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[140px] bg-sticky-white border-2 border-divider rounded-hd-md
        shadow-hd-lg py-1.5 hd-filter"
      style={{
        left: adjustedX,
        top: adjustedY,
        animation: 'fadeSlideDown 0.15s ease-out',
      }}
    >
      {items.map((item, i) => (
        <div key={i}>
          {item.divider && i > 0 && (
            <div className="my-1 mx-2 h-px bg-divider/60" />
          )}
          <button
            onClick={() => { item.onClick(); onClose() }}
            className={`w-full flex items-center gap-2.5 px-3 py-1.5 text-sm text-left
              transition-colors
              ${item.danger
                ? 'text-marker-red hover:bg-marker-red/10'
                : 'text-ink-200 hover:bg-paper-200'
              }
            `}
          >
            <span className="text-base">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        </div>
      ))}
    </div>
  )
}
