/** 历史辩论列表 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { get } from '../api/client'

interface HistoryItem {
  session_id: string
  question: string
  status: string
  perspectives_count: number
  created_at: string
}

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    get<{ items: HistoryItem[] }>('/history')
      .then((res) => setItems(res.items || []))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">历史分析</h1>

      {loading ? (
        <p className="text-gray-500">加载中...</p>
      ) : items.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-gray-500 text-lg mb-2">还没有分析记录</p>
          <Link to="/" className="text-arena-500 hover:underline">开始第一次分析 →</Link>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <Link
              key={item.session_id}
              to={`/result/${item.session_id}`}
              className="block bg-gray-800/30 hover:bg-gray-800/60 border border-gray-700/50 rounded-lg p-4 transition-colors"
            >
              <div className="font-medium text-gray-200 truncate">{item.question}</div>
              <div className="flex gap-4 mt-2 text-xs text-gray-500">
                <span className={item.status === 'completed' ? 'text-green-500' : 'text-yellow-500'}>
                  {item.status === 'completed' ? '✅ 已完成' : '⏳ 进行中'}
                </span>
                <span>{item.perspectives_count} 个视角</span>
                <span>{item.session_id}</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
