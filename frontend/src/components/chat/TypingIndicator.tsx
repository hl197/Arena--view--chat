/** 微信风格 "正在输入..." 动画 */
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
    <div className="flex items-center px-3 mt-2 mb-1">
      {/* 动画点 */}
      <div className="flex items-center gap-1 mr-2">
        <span className="w-[6px] h-[6px] bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-[6px] h-[6px] bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-[6px] h-[6px] bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
      </div>
      <span className="text-xs text-gray-400">{label} 正在输入...</span>
    </div>
  )
}
