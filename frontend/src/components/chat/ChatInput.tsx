/** 微信风格底部输入栏 */
import { useState, useRef, KeyboardEvent } from 'react'

interface ChatInputProps {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

export default function ChatInput({ onSend, disabled, placeholder }: ChatInputProps) {
  const [text, setText] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSend = () => {
    const trimmed = text.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setText('')
    inputRef.current?.focus()
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-[#F7F7F7] border-t border-gray-300">
      <div className="flex items-end gap-2 px-3 py-2 max-w-2xl mx-auto">
        {/* 输入框 */}
        <div className="flex-1 bg-white rounded-lg border border-gray-300 overflow-hidden">
          <input
            ref={inputRef}
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || '参与讨论...'}
            disabled={disabled}
            className="w-full px-3 py-2 text-sm text-gray-900 placeholder-gray-400 outline-none disabled:bg-gray-100"
          />
        </div>

        {/* 发送按钮 */}
        <button
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          className="shrink-0 bg-[#07C160] hover:bg-[#06AD56] disabled:bg-gray-300
                     text-white text-sm font-medium px-5 py-2 rounded-lg transition-colors"
        >
          发送
        </button>
      </div>

      {/* iPhone 底部安全区 */}
      <div className="h-safe-area bg-[#F7F7F7]" />
    </div>
  )
}
