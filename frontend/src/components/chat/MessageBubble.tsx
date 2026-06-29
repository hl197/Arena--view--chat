/** 手绘风格消息气泡——便利贴造型 */
import { useState, useCallback } from 'react'
import type { ChatMessage } from '../../api/types'
import HandDrawnAvatar from '../ui/HandDrawnAvatar'
import MessageContextMenu from './MessageContextMenu'

/** 清理并渲染消息内容——去除 Markdown 语法，保留自然文本 */
function renderContent(text: string): string {
  let html = text
    // 1. 先转义 HTML
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

    // 2. 去除 Markdown 标题标记（整行 ## 开头）
    .replace(/^#{1,6}\s+/gm, '')

    // 3. 去除 Markdown 列表符号（- * + 开头，后面跟空格）
    .replace(/^[\s]*[-*+]\s+/gm, '• ')

    // 4. 去除数字列表（1. 2. 等）
    .replace(/^\d+[\.\)]\s*/gm, '')

    // 5. 去除水平线
    .replace(/^[-*_]{3,}\s*$/gm, '')

    // 6. 去除多余空行（3个以上换行 → 2个换行）
    .replace(/\n{3,}/g, '\n\n')

    // 7. **粗体** → <strong>
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-ink-300">$1</strong>')

    // 8. *斜体* → <em>（但不匹配已经处理的 **）
    .replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em class="text-ink-200">$1</em>')

    // 9. 行内代码 `code` → 保留
    .replace(/`([^`\n]+?)`/g, '<code class="bg-paper-200 rounded px-1 text-xs text-marker-purple">$1</code>')

    // 10. 换行 → <br/>
    .replace(/\n/g, '<br/>')

    // 11. 清理连续的 <br/>（超过2个 → 1个）
    .replace(/(<br\/>){3,}/g, '<br/><br/>')

  return html
}

interface MessageBubbleProps {
  message: ChatMessage
  isConsecutive?: boolean
}

// 根据 senderId 分配头像颜色（稳定伪随机）
const COLORS = ['red', 'blue', 'green', 'purple', 'pink', 'cyan'] as const
const EMOJIS = ['📊', '🧠', '💼', '🎯', '💡', '📚'] as const
const TAPE_COLORS = ['pink', 'blue', 'yellow', 'green', 'purple'] as const

function getAvatarStyle(senderId: string) {
  const hash = senderId.split('').reduce((a, c) => a + c.charCodeAt(0), 0)
  return {
    color: COLORS[hash % COLORS.length],
    emoji: EMOJIS[hash % EMOJIS.length],
    tape: TAPE_COLORS[hash % TAPE_COLORS.length],
  }
}

export default function MessageBubble({ message, isConsecutive }: MessageBubbleProps) {
  const isUser = message.type === 'user'
  const isSystem = message.type === 'system'
  const isJudge = message.senderId?.startsWith('judge')

  const [menuPos, setMenuPos] = useState<{ x: number; y: number } | null>(null)

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    if (isSystem) return  // 系统消息不显示菜单
    e.preventDefault()
    setMenuPos({ x: e.clientX, y: e.clientY })
  }, [isSystem])

  const handleCopy = useCallback(() => {
    const text = message.content
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text)
    } else {
      const ta = document.createElement('textarea')
      ta.value = text
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
  }, [message.content])

  const menuItems = [
    { icon: '📋', label: '复制文字', onClick: handleCopy },
  ]

  // 系统消息
  if (isSystem) {
    return (
      <div className="flex justify-center my-3 px-4">
        <span
          className="text-xs text-ink-50 bg-paper-200/80 rounded-full px-4 py-1.5 border border-dashed border-divider hd-filter"
          dangerouslySetInnerHTML={{ __html: renderContent(message.content) }}
        />
      </div>
    )
  }

  // 用户消息
  if (isUser) {
    return (
      <>
        <div
          className={`flex justify-end px-2 ${isConsecutive ? 'mt-1' : 'mt-4'} cursor-context-menu`}
          onContextMenu={handleContextMenu}
        >
          <div className="max-w-[65%] flex items-start gap-2 flex-row-reverse">
            {/* 头像 */}
            {!isConsecutive && (
              <HandDrawnAvatar content="😊" color="gold" size="md" crown />
            )}
            {isConsecutive && <div className="w-10 shrink-0" />}

            {/* 气泡 */}
            <div className="relative">
              {/* 纸胶带 */}
              <div className="absolute -top-2 right-4 w-10 h-3 bg-marker-gold/40 rounded-sm pointer-events-none" />
              <div
                className="bg-sticky-cream border-2 border-marker-gold/70 rounded-hd-md px-4 py-2.5 text-sm leading-relaxed text-ink-300 shadow-sticky break-words"
                style={{ transform: 'rotate(0.5deg)' }}
                dangerouslySetInnerHTML={{ __html: renderContent(message.content) }}
              />
            </div>
          </div>
        </div>
        {menuPos && (
          <MessageContextMenu
            x={menuPos.x}
            y={menuPos.y}
            items={menuItems}
            onClose={() => setMenuPos(null)}
          />
        )}
      </>
    )
  }

  // Agent / Judge 消息
  const { color, emoji, tape } = getAvatarStyle(message.senderId || 'agent')
  const judgeStyle = isJudge
    ? 'bg-sticky-cream border-marker-gold/60'
    : 'bg-sticky-white border-divider'

  const tapeColorClass = isJudge
    ? 'bg-marker-gold/40'
    : tape === 'pink' ? 'bg-washi-pink/50'
    : tape === 'blue' ? 'bg-washi-blue/50'
    : tape === 'yellow' ? 'bg-washi-yellow/50'
    : tape === 'green' ? 'bg-washi-green/50'
    : 'bg-marker-purple/30'

  return (
    <>
      <div
        className={`flex px-2 ${isConsecutive ? 'mt-1' : 'mt-4'} cursor-context-menu`}
        onContextMenu={handleContextMenu}
      >
        <div className="flex items-start gap-2">
          {/* 头像 */}
          {!isConsecutive && (
            <HandDrawnAvatar
              content={message.avatar || emoji}
              color={isJudge ? 'gold' : color}
              size="md"
            />
          )}
          {isConsecutive && <div className="w-10 shrink-0" />}

          {/* 气泡 */}
          <div className="max-w-[65%]">
            {!isConsecutive && (
              <div className="text-xs text-ink-50 mb-1.5 ml-1 font-medium flex items-center gap-1.5">
                <span>{message.senderName}</span>
                {isJudge && (
                  <span className="text-marker-gold text-[10px] bg-marker-gold/15 px-1.5 py-0.5 rounded-full">
                    ⚖️ 裁判
                  </span>
                )}
              </div>
            )}
            <div className="relative">
              {/* 纸胶带 */}
              <div className={`absolute -top-2 left-4 w-10 h-3 ${tapeColorClass} rounded-sm pointer-events-none`} />
              <div
                className={`border-2 rounded-hd-md px-4 py-2.5 text-sm leading-relaxed text-ink-300 shadow-sticky break-words ${judgeStyle}`}
                style={{ transform: 'rotate(-0.6deg)' }}
                dangerouslySetInnerHTML={{ __html: renderContent(message.content) }}
              />
            </div>
          </div>
        </div>
      </div>
      {menuPos && (
        <MessageContextMenu
          x={menuPos.x}
          y={menuPos.y}
          items={menuItems}
          onClose={() => setMenuPos(null)}
        />
      )}
    </>
  )
}
