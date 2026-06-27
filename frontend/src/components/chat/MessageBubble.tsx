/** 微信风格消息气泡——Agent左侧，用户右侧 */
import type { ChatMessage } from '../../api/types'

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
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>')

    // 8. *斜体* → <em>（但不匹配已经处理的 **）
    .replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em>$1</em>')

    // 9. 行内代码 `code` → 保留
    .replace(/`([^`\n]+?)`/g, '<code class="bg-gray-200 rounded px-1 text-xs">$1</code>')

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

export default function MessageBubble({ message, isConsecutive }: MessageBubbleProps) {
  const isUser = message.type === 'user'
  const isSystem = message.type === 'system'
  const isJudge = message.senderId?.startsWith('judge')

  if (isSystem) {
    return (
      <div className="flex justify-center my-2 px-4">
        <span
          className="text-xs text-gray-400 bg-gray-200/60 rounded px-3 py-1"
          dangerouslySetInnerHTML={{ __html: renderContent(message.content) }}
        />
      </div>
    )
  }

  if (isUser) {
    return (
      <div className={`flex justify-end px-3 ${isConsecutive ? 'mt-[2px]' : 'mt-3'}`}>
        <div className="max-w-[70%]">
          <div
            className="bg-[#95EC69] text-gray-900 rounded-lg px-3 py-2 text-sm leading-relaxed break-words shadow-sm"
            dangerouslySetInnerHTML={{ __html: renderContent(message.content) }}
          />
        </div>
      </div>
    )
  }

  const avatarMap: Record<string, string> = {
    p_01: '/avatars/cautious.png',
    p_02: '/avatars/seeker.png',
    p_03: '/avatars/analyst.png',
    p_04: '/avatars/humanist.png',
    p_05: '/avatars/thinker.png',
    p_06: '/avatars/pragmatist.png',
    judge: '/avatars/thinker.png',
  }

  const avatarSrc = message.avatar || avatarMap[message.senderId] || '/avatars/analyst.png'

  return (
    <div className={`flex px-3 ${isConsecutive ? 'mt-[2px]' : 'mt-3'}`}>
      <div className="shrink-0 mr-2">
        {!isConsecutive && (
          <img
            src={avatarSrc}
            alt={message.senderName}
            className="w-10 h-10 rounded-md object-cover"
            onError={(e) => {
              (e.target as HTMLImageElement).src = '/avatars/analyst.png'
            }}
          />
        )}
        {isConsecutive && <div className="w-10" />}
      </div>

      <div className="max-w-[65%]">
        {!isConsecutive && (
          <div className="text-xs text-gray-500 mb-1 ml-1">
            {message.senderName}
            {isJudge && (
              <span className="text-amber-600 ml-1">⚖️ 裁判</span>
            )}
          </div>
        )}
        <div
          className={`rounded-lg px-3 py-2 text-sm leading-relaxed break-words shadow-sm ${
            isJudge ? 'bg-amber-50 border border-amber-300 text-gray-900' : 'bg-white text-gray-900'
          }`}
          dangerouslySetInnerHTML={{ __html: renderContent(message.content) }}
        />
      </div>
    </div>
  )
}
