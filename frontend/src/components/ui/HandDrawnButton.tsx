import { ButtonHTMLAttributes, ReactNode } from 'react'

interface HandDrawnButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  tilt?: 'left' | 'right' | 'none'
  fullWidth?: boolean
  children: ReactNode
}

/**
 * 手绘风格按钮
 * - 不规则圆角 + 手绘边框（SVG filter）
 * - hover 轻微按压效果
 * - 可选择倾斜角度（更像手绘）
 */
export default function HandDrawnButton({
  variant = 'primary',
  size = 'md',
  tilt = 'none',
  fullWidth = false,
  children,
  className = '',
  disabled,
  ...props
}: HandDrawnButtonProps) {
  const base = 'relative font-medium transition-all duration-200 hd-filter select-none'

  const variants = {
    primary: 'bg-marker-blue text-white border-hd border-ink-300 hover:bg-marker-blue/90 active:translate-y-0.5 active:shadow-hd-sm hover:-translate-y-0.5 shadow-hd-sm',
    secondary: 'bg-paper-50 text-ink-300 border-hd border-divider hover:bg-paper-100 active:translate-y-0.5 hover:-translate-y-0.5 shadow-hd-sm',
    outline: 'bg-transparent text-ink-300 border-hd border-ink-300 hover:bg-ink-300/5 active:translate-y-0.5 hover:-translate-y-0.5',
    danger: 'bg-marker-red text-white border-hd border-ink-300 hover:bg-marker-red/90 active:translate-y-0.5 hover:-translate-y-0.5 shadow-hd-sm',
    ghost: 'bg-transparent text-ink-200 border-transparent hover:bg-paper-200 border-hd active:translate-y-0.5',
  }

  const sizes = {
    sm: 'px-3 py-1.5 text-sm rounded-hd-sm',
    md: 'px-4 py-2 text-sm rounded-hd-md',
    lg: 'px-6 py-3 text-base rounded-hd-lg',
  }

  const tilts = {
    left: 'hover:rotate-[-1deg]',
    right: 'hover:rotate-1deg',
    none: '',
  }

  return (
    <button
      className={`
        ${base}
        ${variants[variant]}
        ${sizes[size]}
        ${tilts[tilt]}
        ${fullWidth ? 'w-full' : ''}
        ${disabled ? 'opacity-50 cursor-not-allowed hover:translate-y-0 hover:rotate-0' : 'cursor-pointer'}
        ${className}
      `}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  )
}
