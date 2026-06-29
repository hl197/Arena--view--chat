import { InputHTMLAttributes, TextareaHTMLAttributes, forwardRef } from 'react'

interface BaseProps {
  variant?: 'default' | 'filled'
  label?: string
  error?: string
}

interface HandDrawnInputProps extends InputHTMLAttributes<HTMLInputElement>, BaseProps {}
interface HandDrawnTextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement>, BaseProps {
  rows?: number
}

/**
 * 手绘风格输入框
 * - 手绘边框（SVG filter）
 * - focus 时边框变粗、变色
 */
export const HandDrawnInput = forwardRef<HTMLInputElement, HandDrawnInputProps>(function HandDrawnInput(
  { variant = 'default', label, error, className = '', ...props },
  ref,
) {
  const base = 'w-full px-4 py-2.5 rounded-hd-md outline-none transition-all duration-200 text-ink-300 hd-filter text-sm'

  const variants = {
    default: 'bg-sticky-white border-2 border-divider focus:border-marker-blue focus:shadow-[2px_2px_0_rgba(91,141,239,0.2)]',
    filled: 'bg-paper-100 border-2 border-divider focus:border-marker-blue focus:bg-sticky-white',
  }

  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm text-ink-100 mb-1.5 font-medium">
          {label}
        </label>
      )}
      <input
        ref={ref}
        className={`${base} ${variants[variant]} ${error ? 'border-marker-red' : ''} ${className}`}
        {...props}
      />
      {error && (
        <p className="mt-1.5 text-xs text-marker-red">{error}</p>
      )}
    </div>
  )
})

/**
 * 手绘风格多行文本框
 */
export const HandDrawnTextarea = forwardRef<HTMLTextAreaElement, HandDrawnTextareaProps>(function HandDrawnTextarea(
  { variant = 'default', label, error, rows = 4, className = '', ...props },
  ref,
) {
  const base = 'w-full px-4 py-3 rounded-hd-md outline-none transition-all duration-200 text-ink-300 hd-filter text-sm resize-none'

  const variants = {
    default: 'bg-sticky-white border-2 border-divider focus:border-marker-blue focus:shadow-[2px_2px_0_rgba(91,141,239,0.2)]',
    filled: 'bg-paper-100 border-2 border-divider focus:border-marker-blue focus:bg-sticky-white',
  }

  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm text-ink-100 mb-1.5 font-medium">
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        rows={rows}
        className={`${base} ${variants[variant]} ${error ? 'border-marker-red' : ''} ${className}`}
        {...props}
      />
      {error && (
        <p className="mt-1.5 text-xs text-marker-red">{error}</p>
      )}
    </div>
  )
})

export default HandDrawnInput
