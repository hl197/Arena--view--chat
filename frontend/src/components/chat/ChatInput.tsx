/** 手绘风格底部输入栏 */
import { useState, useRef, KeyboardEvent } from 'react'
import HandDrawnButton from '../ui/HandDrawnButton'

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
    <div className="bg-paper-100 border-t-2 border-dashed border-divider/70 p-3">
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        {/* 输入框 */}
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || '说说你的想法...'}
            disabled={disabled}
            className="w-full px-4 py-2.5 bg-sticky-white border-2 border-divider rounded-hd-md
                       text-sm text-ink-300 placeholder-ink-50 outline-none
                       focus:border-marker-blue focus:shadow-[2px_2px_0_rgba(91,141,239,0.2)]
                       disabled:bg-paper-200 disabled:cursor-not-allowed
                       hd-filter transition-all duration-200"
          />
        </div>

        {/* 发送按钮 */}
        <HandDrawnButton
          variant="primary"
          size="md"
          onClick={handleSend}
          disabled={disabled || !text.trim()}
          tilt="left"
        >
          发送 →
        </HandDrawnButton>
      </div>
    </div>
  )
}
