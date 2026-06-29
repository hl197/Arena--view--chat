/** 手绘风格 "正在输入..." 动画 */
interface TypingIndicatorProps {
  names: string[]
}

export default function TypingIndicator({ names }: TypingIndicatorProps) {
  if (names.length === 0) return null

  const label = names.length === 1
    ? `${names[0]}`
    : names.length === 2
    ? `${names[0]}、${names[1]}`
    : `${names[0]}等${names.length}人`

  return (
    <div className="flex items-center px-4 mt-3 mb-1">
      {/* 动画点 */}
      <div className="flex items-center gap-1 mr-2 bg-sticky-white border-2 border-divider rounded-full px-2.5 py-1 hd-filter">
        <span className="w-1.5 h-1.5 bg-marker-blue rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-1.5 h-1.5 bg-marker-purple rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-1.5 h-1.5 bg-marker-green rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
      <span className="text-xs text-ink-50">{label} 正在思考...</span>
    </div>
  )
}
