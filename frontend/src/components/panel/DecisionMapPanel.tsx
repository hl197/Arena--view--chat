/** 右侧面板 — 决策地图
 *
 *  简易 Markdown 渲染 + 复制按钮
 */

import { useState, useMemo } from 'react'
import HandDrawnButton from '../ui/HandDrawnButton'

interface DecisionMapPanelProps {
  content: string
}

/** 极简 Markdown → HTML 渲染
 *  支持：标题(#/##/###)、粗体(** **)、列表(- / 1.)、换行
 */
function renderMarkdown(text: string): Array<{ type: string; content: string; level?: number; ordered?: boolean }> {
  const lines = text.split('\n')
  const blocks: Array<{ type: string; content: string; level?: number; ordered?: boolean }> = []
  let listBuffer: string[] = []
  let listType: 'ul' | 'ol' | null = null

  const flushList = () => {
    if (listBuffer.length > 0 && listType) {
      blocks.push({
        type: listType,
        content: listBuffer.join('|||'),
        ordered: listType === 'ol',
      })
      listBuffer = []
      listType = null
    }
  }

  for (const line of lines) {
    const trimmed = line.trim()

    // 标题
    if (trimmed.startsWith('### ')) {
      flushList()
      blocks.push({ type: 'h3', content: trimmed.slice(4) })
      continue
    }
    if (trimmed.startsWith('## ')) {
      flushList()
      blocks.push({ type: 'h2', content: trimmed.slice(3) })
      continue
    }
    if (trimmed.startsWith('# ')) {
      flushList()
      blocks.push({ type: 'h1', content: trimmed.slice(2) })
      continue
    }

    // 无序列表
    if (/^[-•] /.test(trimmed)) {
      if (listType !== 'ul') flushList()
      listType = 'ul'
      listBuffer.push(trimmed.replace(/^[-•] /, ''))
      continue
    }

    // 有序列表
    if (/^\d+\.\s/.test(trimmed)) {
      if (listType !== 'ol') flushList()
      listType = 'ol'
      listBuffer.push(trimmed.replace(/^\d+\.\s/, ''))
      continue
    }

    // 空行
    if (trimmed === '') {
      flushList()
      continue
    }

    // 普通段落
    flushList()
    blocks.push({ type: 'p', content: trimmed })
  }

  flushList()
  return blocks
}

/** 行内粗体渲染 */
function renderInline(text: string, key?: string) {
  // 支持 **bold** 和 *italic*
  const parts: Array<{ text: string; bold?: boolean; italic?: boolean }> = []
  let remaining = text
  const boldRe = /\*\*(.+?)\*\*/g

  let lastIndex = 0
  let match
  while ((match = boldRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ text: text.slice(lastIndex, match.index) })
    }
    parts.push({ text: match[1], bold: true })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < text.length) {
    parts.push({ text: text.slice(lastIndex) })
  }

  if (parts.length === 0) return text

  return parts.map((p, i) =>
    p.bold ? <strong key={i} className="font-bold text-ink-300">{p.text}</strong> : <span key={i}>{p.text}</span>
  )
}

export default function DecisionMapPanel({ content }: DecisionMapPanelProps) {
  const [copied, setCopied] = useState(false)

  const blocks = useMemo(() => renderMarkdown(content), [content])

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // 兼容方案
      const ta = document.createElement('textarea')
      ta.value = content
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (!content) {
    return (
      <div className="text-sm text-ink-50 text-center py-12">
        <p className="text-3xl mb-3">🗺️</p>
        <p className="font-hand text-base mb-1">决策地图生成中</p>
        <p className="text-xs opacity-70">裁判正在综合所有观点...</p>
        <div className="flex gap-1 justify-center mt-3">
          <span className="w-2 h-2 rounded-full bg-marker-blue animate-bounce" style={{ animationDelay: '0ms' }} />
          <span className="w-2 h-2 rounded-full bg-marker-purple animate-bounce" style={{ animationDelay: '150ms' }} />
          <span className="w-2 h-2 rounded-full bg-marker-green animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* 标题栏 */}
      <div className="flex items-center justify-between sticky top-0 bg-paper-100 pb-2 z-10">
        <div className="flex items-center gap-2">
          <span className="text-lg">📊</span>
          <span className="font-hand font-bold text-ink-300">决策地图</span>
        </div>
        <HandDrawnButton
          variant="outline"
          size="sm"
          onClick={handleCopy}
        >
          {copied ? '✓ 已复制' : '📋 复制'}
        </HandDrawnButton>
      </div>

      {/* 决策地图内容 */}
      <div className="space-y-3 text-sm text-ink-200 leading-relaxed">
        {blocks.map((block, i) => {
          switch (block.type) {
            case 'h1':
              return (
                <h1 key={i} className="text-lg font-bold font-hand text-ink-300 pt-2 pb-1 border-b-2 border-dashed border-divider">
                  {renderInline(block.content)}
                </h1>
              )
            case 'h2':
              return (
                <h2 key={i} className="text-base font-bold font-hand text-ink-300 pt-2 flex items-center gap-2">
                  <span className="w-1 h-5 bg-marker-blue rounded-full" />
                  {renderInline(block.content)}
                </h2>
              )
            case 'h3':
              return (
                <h3 key={i} className="text-sm font-bold text-marker-blue pt-1">
                  {renderInline(block.content)}
                </h3>
              )
            case 'p':
              return (
                <p key={i} className="text-ink-200">
                  {renderInline(block.content)}
                </p>
              )
            case 'ul':
              return (
                <ul key={i} className="space-y-1.5 pl-1">
                  {block.content.split('|||').map((item, j) => (
                    <li key={j} className="flex gap-2">
                      <span className="text-marker-blue shrink-0 mt-0.5">•</span>
                      <span>{renderInline(item)}</span>
                    </li>
                  ))}
                </ul>
              )
            case 'ol':
              return (
                <ol key={i} className="space-y-1.5 pl-1 list-decimal list-inside">
                  {block.content.split('|||').map((item, j) => (
                    <li key={j} className="text-ink-200">
                      {renderInline(item)}
                    </li>
                  ))}
                </ol>
              )
            default:
              return null
          }
        })}
      </div>

      {/* 底部说明 */}
      <div className="pt-3 border-t border-dashed border-divider mt-4">
        <p className="text-[11px] text-ink-50 font-hand">
          💡 决策地图由 AI 综合多视角生成，仅供参考。最终决策请结合自身情况判断。
        </p>
      </div>
    </div>
  )
}
