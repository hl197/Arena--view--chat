/** 结果页 — 展示完整决策地图 */

import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { get } from '../api/client'

export default function ResultPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!sessionId) return
    get<Record<string, unknown>>(`/debate/${sessionId}/result`)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [sessionId])

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto text-center py-20">
        <div className="animate-spin text-4xl mb-4">⚔️</div>
        <p className="text-gray-400">加载结果中...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto text-center py-20">
        <p className="text-red-400 mb-4">加载失败: {error}</p>
        <Link to="/" className="text-arena-500 hover:underline">返回首页</Link>
      </div>
    )
  }

  if (!data) return null

  const decisionMap = (data.decision_map as string) || ''
  const perspectives = (data.perspectives as Array<Record<string, unknown>>) || []
  const debateTranscript = (data.debate_transcript as Array<Record<string, unknown>>) || []
  const totalTokens = (data.total_tokens as number) || 0
  const totalTimeMs = (data.total_time_ms as number) || 0

  // 解析决策地图的段落
  const sections = decisionMap
    ? decisionMap
        .split(/\n(?=##?\s+|#\s+)/)
        .filter(Boolean)
        .map((s) => s.trim())
    : []

  return (
    <div className="max-w-4xl mx-auto">
      {/* 头部 */}
      <div className="mb-8">
        <Link to="/" className="text-sm text-gray-500 hover:text-gray-300 mb-4 inline-block">
          ← 返回首页
        </Link>
        <h1 className="text-2xl font-bold mt-2">决策分析结果</h1>
        <div className="flex gap-4 mt-2 text-sm text-gray-500">
          <span>问题: {data.question as string}</span>
          <span>·</span>
          <span>{perspectives.length} 个视角</span>
          <span>·</span>
          <span>{debateTranscript.length} 轮辩论</span>
          <span>·</span>
          <span>{(totalTimeMs / 1000).toFixed(1)}s</span>
          <span>·</span>
          <span>{totalTokens.toLocaleString()} tokens</span>
        </div>
      </div>

      {/* 决策地图 */}
      {sections.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-8">
          {sections.map((section, i) => {
            // 判断段落类型
            const isHeader = section.match(/^#{1,3}\s+/)
            return (
              <div
                key={i}
                className={`mb-6 last:mb-0 animate-fade-in ${
                  isHeader ? '' : 'prose prose-invert prose-sm max-w-none'
                }`}
                style={{ animationDelay: `${i * 100}ms` }}
              >
                {isHeader ? (
                  <h2 className="text-lg font-bold text-gray-200 mt-6 mb-3 border-b border-gray-800 pb-2">
                    {section.replace(/^#{1,3}\s+/, '')}
                  </h2>
                ) : (
                  <div className="text-gray-300 leading-relaxed whitespace-pre-wrap text-sm">
                    {section}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* 参与视角 */}
      <div className="mb-8">
        <h2 className="text-lg font-bold mb-4">参与辩论的视角</h2>
        <div className="grid gap-3">
          {perspectives.map((p, i) => (
            <div key={i} className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
              <div className="font-medium text-gray-200">{p.name as string}</div>
              <div className="text-sm text-gray-400 mt-1">{p.stance as string}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 辩论记录 */}
      {debateTranscript.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-bold mb-4">交叉质询记录</h2>
          <div className="space-y-4">
            {debateTranscript.map((turn, i) => (
              <div key={i} className="bg-gray-800/30 border border-gray-700/50 rounded-lg p-4">
                <div className="text-xs text-gray-500 mb-2">
                  第 {(turn.round as number)} 轮 · {turn.challenger_name as string} 质疑 {turn.defender_name as string}
                </div>
                <div className="grid gap-2 text-sm">
                  <div>
                    <span className="text-yellow-500 font-medium">质疑:</span>
                    <p className="text-gray-300 mt-1">{(turn.challenge as string)?.slice(0, 300)}</p>
                  </div>
                  <div>
                    <span className="text-blue-500 font-medium">回应:</span>
                    <p className="text-gray-300 mt-1">{(turn.defense as string)?.slice(0, 300)}</p>
                  </div>
                  {(turn.judge_note as string) && (
                    <div>
                      <span className="text-green-500 font-medium">裁判:</span>
                      <p className="text-gray-400 mt-1 text-xs">{turn.judge_note as string}</p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 分享 */}
      <div className="text-center py-12 border-t border-gray-800">
        <p className="text-gray-500 mb-4">分享这个分析</p>
        <button
          onClick={() => {
            navigator.clipboard.writeText(window.location.href)
          }}
          className="bg-gray-800 hover:bg-gray-700 text-gray-300 px-6 py-2 rounded-lg transition-colors text-sm"
        >
          复制链接
        </button>
      </div>
    </div>
  )
}
