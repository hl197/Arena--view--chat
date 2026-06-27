/** Agent 状态栏——显示每个角色的实时状态（微信风格） */

interface AgentState {
  id: string
  name: string
  avatar: string
  status: 'idle' | 'thinking' | 'searching' | 'composing' | 'debating' | 'done' | 'error'
}

interface AgentStatusBarProps {
  agents: AgentState[]
  phase?: string
}

const STATUS_CONFIG: Record<string, { emoji: string; label: string; color: string }> = {
  idle:      { emoji: '⏳', label: '等待中',   color: 'text-gray-400' },
  thinking:  { emoji: '🤔', label: '思考中',   color: 'text-yellow-500' },
  searching: { emoji: '🔍', label: '搜索中',   color: 'text-blue-500' },
  composing: { emoji: '✍️', label: '输入中',   color: 'text-green-500' },
  debating:  { emoji: '⚔️', label: '辩论中',   color: 'text-orange-500' },
  done:      { emoji: '✅', label: '已完成',   color: 'text-emerald-500' },
  error:     { emoji: '❌', label: '出错',     color: 'text-red-500' },
}

export type { AgentState }
export { STATUS_CONFIG }

export default function AgentStatusBar({ agents, phase }: AgentStatusBarProps) {
  if (agents.length === 0) return null

  const phaseLabel = (() => {
    switch (phase) {
      case 'perspectives': return '🎯 生成分析视角'
      case 'research': return '📚 各视角独立研究'
      case 'debate': return '⚔️ 交叉辩论'
      case 'synthesis': return '🧠 裁判合成决策地图'
      default: return null
    }
  })()

  return (
    <div className="bg-white border-b border-gray-200 px-3 py-2">
      {/* 当前阶段 */}
      {phaseLabel && (
        <div className="text-xs text-gray-500 mb-2 text-center">{phaseLabel}</div>
      )}

      {/* Agent 状态列表——可横向滚动 */}
      <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
        {agents.map((agent) => {
          const config = STATUS_CONFIG[agent.status] || STATUS_CONFIG.idle
          const isActive = !['idle', 'done', 'error'].includes(agent.status)

          return (
            <div
              key={agent.id}
              className={`flex items-center gap-1.5 shrink-0 px-2 py-1 rounded-full text-xs
                transition-all duration-500 ${
                isActive
                  ? 'bg-gray-100 scale-105'
                  : 'bg-transparent'
              }`}
            >
              {/* 头像小图 */}
              <img
                src={agent.avatar}
                alt={agent.name}
                className={`w-5 h-5 rounded object-cover ${
                  isActive ? 'ring-2 ring-offset-1 ring-blue-400' : 'opacity-60'
                }`}
                onError={(e) => {
                  (e.target as HTMLImageElement).src = '/avatars/analyst.png'
                }}
              />

              {/* 名字 + 状态 */}
              <span className="text-gray-700 whitespace-nowrap">{agent.name}</span>
              <span className={`${config.color} whitespace-nowrap`}>
                {config.emoji} {config.label}
              </span>

              {/* 活跃状态动画点 */}
              {isActive && (
                <span className="flex gap-0.5 ml-0.5">
                  <span className="w-1 h-1 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1 h-1 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1 h-1 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
