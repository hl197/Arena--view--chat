/** Agent 状态栏——手绘风格 */

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

const STATUS_CONFIG: Record<string, { emoji: string; label: string; color: string; bg: string }> = {
  idle:      { emoji: '⏳', label: '等待中',   color: 'text-ink-50', bg: 'bg-paper-200' },
  thinking:  { emoji: '🤔', label: '思考中',   color: 'text-amber-600', bg: 'bg-marker-yellow/20' },
  searching: { emoji: '🔍', label: '搜索中',   color: 'text-marker-blue', bg: 'bg-marker-blue/15' },
  composing: { emoji: '✍️', label: '写作中',   color: 'text-marker-green', bg: 'bg-marker-green/15' },
  debating:  { emoji: '⚔️', label: '辩论中',   color: 'text-marker-red', bg: 'bg-marker-red/15' },
  done:      { emoji: '✅', label: '已完成',   color: 'text-marker-green', bg: 'bg-paper-200' },
  error:     { emoji: '❌', label: '出错',     color: 'text-marker-red', bg: 'bg-marker-red/10' },
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
    <div className="bg-paper-50 border-b-2 border-dashed border-divider/60 px-4 py-2">
      {/* 当前阶段 */}
      {phaseLabel && (
        <div className="text-xs text-ink-50 mb-2 text-center font-medium">{phaseLabel}</div>
      )}

      {/* Agent 状态列表——可横向滚动 */}
      <div className="flex gap-2 overflow-x-auto pb-1 hd-scrollbar">
        {agents.map((agent) => {
          const config = STATUS_CONFIG[agent.status] || STATUS_CONFIG.idle
          const isActive = !['idle', 'done', 'error'].includes(agent.status)

          return (
            <div
              key={agent.id}
              className={`flex items-center gap-1.5 shrink-0 px-3 py-1.5 rounded-full text-xs
                border-2 hd-filter transition-all duration-300
                ${isActive
                  ? `${config.bg} border-divider scale-105 shadow-hd-sm`
                  : 'bg-transparent border-transparent'
                }
              `}
            >
              {/* 头像小图 */}
              <span className="text-base">
                {agent.avatar?.startsWith('http') || agent.avatar?.startsWith('/')
                  ? <img src={agent.avatar} alt="" className="w-5 h-5 rounded-full object-cover" />
                  : agent.avatar || '🤖'
                }
              </span>

              {/* 名字 + 状态 */}
              <span className="text-ink-200 whitespace-nowrap font-medium">{agent.name}</span>
              <span className={`${config.color} whitespace-nowrap text-[11px]`}>
                {config.emoji} {config.label}
              </span>

              {/* 活跃状态动画点 */}
              {isActive && (
                <span className="flex gap-0.5 ml-0.5">
                  <span className="w-1 h-1 bg-marker-blue rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1 h-1 bg-marker-purple rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1 h-1 bg-marker-green rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
