import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import HandDrawnButton from '../ui/HandDrawnButton'
import { HandDrawnInput } from '../ui/HandDrawnInput'
import HandDrawnDivider from '../ui/HandDrawnDivider'
import HistoryCard from './HistoryCard'
import { get, del } from '../../api/client'
import { useUIStore } from '../../store/uiStore'

interface HistoryItem {
  session_id: string
  question: string
  status: 'completed' | 'processing' | 'running' | 'error'
  perspectives_count: number
  created_at: string
}

interface HistorySidebarProps {
  activeSessionId?: string
  onSelect?: (sessionId: string) => void
  generating?: boolean  // 正在生成决策时禁用切换
}

function formatTime(isoStr: string): string {
  const date = new Date(isoStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const mins = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  if (hours < 24) return `${hours} 小时前`
  if (days < 2) return '昨天'
  if (days < 7) return `${days} 天前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function groupByTime(items: HistoryItem[]): { today: HistoryItem[]; yesterday: HistoryItem[]; earlier: HistoryItem[] } {
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - 86400000

  const today: HistoryItem[] = []
  const yesterday: HistoryItem[] = []
  const earlier: HistoryItem[] = []

  for (const item of items) {
    const t = new Date(item.created_at).getTime()
    if (t >= todayStart) today.push(item)
    else if (t >= yesterdayStart) yesterday.push(item)
    else earlier.push(item)
  }

  return { today, yesterday, earlier }
}

export default function HistorySidebar({ activeSessionId, onSelect, generating }: HistorySidebarProps) {
  const navigate = useNavigate()
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const { sidebarCollapsed, toggleSidebar } = useUIStore()

  useEffect(() => {
    loadHistory()
  }, [])

  const loadHistory = async () => {
    setLoading(true)
    try {
      const res = await get<{ items: HistoryItem[]; total: number }>('/history?page_size=50')
      setHistory(res.items || [])
    } catch {
      // 静默失败
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (sessionId: string, e?: React.MouseEvent) => {
    e?.stopPropagation()
    try {
      await del(`/history/${sessionId}`)
      setHistory((prev) => prev.filter((i) => i.session_id !== sessionId))
    } catch (err) {
      console.error('删除失败:', err)
    }
  }

  const handleSelect = (sessionId: string) => {
    onSelect?.(sessionId)
  }

  const handleNewChat = () => {
    navigate('/')
  }

  const filtered = search.trim()
    ? history.filter((h) => h.question.toLowerCase().includes(search.toLowerCase()))
    : history

  const { today, yesterday, earlier } = groupByTime(filtered)

  // 折叠状态：只显示图标
  if (sidebarCollapsed) {
    return (
      <div className="w-14 h-full bg-paper-200 border-r-2 border-divider flex flex-col items-center py-3 gap-2 hd-filter">
        <button
          onClick={handleNewChat}
          className="w-10 h-10 rounded-full bg-marker-blue text-white flex items-center justify-center text-lg hover:scale-110 transition-transform shadow-hd-sm"
          title="新建讨论"
        >
          +
        </button>
        <HandDrawnDivider variant="line" className="w-10 my-1" />
        <div className="flex-1 overflow-y-auto hd-scrollbar w-full px-2 flex flex-col gap-2 items-center">
          {history.slice(0, 20).map((item, i) => {
            const colors = ['red', 'blue', 'green', 'purple', 'gold', 'pink', 'cyan']
            const emojis = ['📊', '🧠', '💼', '⚖️', '🎯', '💡', '📚']
            const idx = i % 7
            return (
              <div
                key={item.session_id}
                onClick={() => handleSelect(item.session_id)}
                className={`w-10 h-10 rounded-full flex items-center justify-center text-base cursor-pointer transition-all hover:scale-110 ${
                  activeSessionId === item.session_id
                    ? 'bg-marker-gold/30 border-2 border-marker-gold'
                    : 'bg-sticky-white border-2 border-divider hover:border-marker-blue/60'
                }`}
                title={item.question}
              >
                {emojis[idx]}
              </div>
            )
          })}
        </div>
        <button
          onClick={toggleSidebar}
          className="w-10 h-10 rounded-full bg-paper-100 border-2 border-divider flex items-center justify-center text-ink-100 hover:bg-paper-50 transition-colors"
          title="展开侧边栏"
        >
          →
        </button>
      </div>
    )
  }

  return (
    <div className="h-full bg-paper-200 border-r-2 border-divider flex flex-col relative">
      {/* 纸胶带装饰 */}
      <div className="absolute top-0 -right-1.5 w-3 h-full bg-washi-pink/30 pointer-events-none z-10" />

      {/* 顶部：新建按钮 */}
      <div className="p-3 border-b-2 border-dashed border-divider/60">
        <HandDrawnButton
          variant="primary"
          size="md"
          fullWidth
          tilt="right"
          onClick={handleNewChat}
          disabled={generating}
        >
          ✏️ 新建讨论
        </HandDrawnButton>
      </div>

      {/* 搜索 */}
      <div className="px-3 py-3">
        <HandDrawnInput
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="🔍 搜索历史..."
          variant="filled"
        />
      </div>

      {/* 历史列表 */}
      <div className="flex-1 overflow-y-auto hd-scrollbar px-3 pb-3 space-y-4">
        {loading && (
          <div className="text-center text-ink-50 text-sm py-8">加载中...</div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="text-center py-8">
            <div className="text-3xl mb-2">📒</div>
            <p className="text-ink-50 text-sm">还没有讨论记录</p>
            <p className="text-ink-50 text-xs mt-1">点击上方按钮开始</p>
          </div>
        )}

        {today.length > 0 && (
          <div>
            <div className="text-xs font-bold text-ink-50 mb-2 px-1 tracking-wider">今天</div>
            <div className="space-y-2.5">
              {today.map((item) => (
                <HistoryCard
                  key={item.session_id}
                  sessionId={item.session_id}
                  title={item.question}
                  status={item.status as any}
                  perspectivesCount={item.perspectives_count || 5}
                  timeLabel={formatTime(item.created_at)}
                  active={activeSessionId === item.session_id}
                  onClick={() => handleSelect(item.session_id)}
                  onDelete={() => handleDelete(item.session_id)}
                />
              ))}
            </div>
          </div>
        )}

        {yesterday.length > 0 && (
          <div>
            <div className="text-xs font-bold text-ink-50 mb-2 px-1 tracking-wider">昨天</div>
            <div className="space-y-2.5">
              {yesterday.map((item) => (
                <HistoryCard
                  key={item.session_id}
                  sessionId={item.session_id}
                  title={item.question}
                  status={item.status as any}
                  perspectivesCount={item.perspectives_count || 5}
                  timeLabel={formatTime(item.created_at)}
                  active={activeSessionId === item.session_id}
                  onClick={() => handleSelect(item.session_id)}
                  onDelete={() => handleDelete(item.session_id)}
                />
              ))}
            </div>
          </div>
        )}

        {earlier.length > 0 && (
          <div>
            <div className="text-xs font-bold text-ink-50 mb-2 px-1 tracking-wider">更早</div>
            <div className="space-y-2.5">
              {earlier.map((item) => (
                <HistoryCard
                  key={item.session_id}
                  sessionId={item.session_id}
                  title={item.question}
                  status={item.status as any}
                  perspectivesCount={item.perspectives_count || 5}
                  timeLabel={formatTime(item.created_at)}
                  active={activeSessionId === item.session_id}
                  onClick={() => handleSelect(item.session_id)}
                  onDelete={() => handleDelete(item.session_id)}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 底部折叠按钮 */}
      <div className="p-2 border-t-2 border-dashed border-divider/60">
        <button
          onClick={toggleSidebar}
          className="w-full py-1.5 text-xs text-ink-50 hover:text-ink-200 transition-colors flex items-center justify-center gap-1"
        >
          ← 收起侧边栏
        </button>
      </div>
    </div>
  )
}
