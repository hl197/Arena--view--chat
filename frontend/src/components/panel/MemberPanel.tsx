/** 右侧面板 — 成员列表 */
import HandDrawnAvatar from '../ui/HandDrawnAvatar'
import HandDrawnBadge from '../ui/HandDrawnBadge'
import type { AgentStateItem } from '../../store/debateStore'

interface MemberPanelProps {
  perspectives: Array<{ id: string; name: string; stance?: string }>
  agentStates: AgentStateItem[]
  judgeState: AgentStateItem | null
}

const STATUS_LABELS: Record<string, { label: string; variant: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'gold' }> = {
  idle:      { label: '等待中', variant: 'default' },
  thinking:  { label: '思考中', variant: 'warning' },
  searching: { label: '搜索中', variant: 'info' },
  composing: { label: '写作中', variant: 'info' },
  debating:  { label: '辩论中', variant: 'danger' },
  done:      { label: '已完成', variant: 'success' },
  error:     { label: '出错', variant: 'danger' },
}

const AVATAR_COLORS: Array<'red' | 'blue' | 'green' | 'yellow' | 'purple' | 'pink' | 'cyan'> = [
  'blue', 'pink', 'green', 'yellow', 'purple', 'red', 'cyan',
]

export default function MemberPanel({ perspectives, agentStates, judgeState }: MemberPanelProps) {
  const totalMembers = 1 + perspectives.length + (judgeState ? 1 : 0)

  return (
    <div className="space-y-4">
      {/* 统计 */}
      <div className="bg-sticky-white/70 p-3 rounded-hd-md border-2 border-divider hd-filter tilt-left">
        <div className="text-xs text-ink-50 mb-1 font-hand">👥 群聊成员</div>
        <div className="text-lg font-bold text-ink-300 font-hand">{totalMembers} 人</div>
        <div className="text-[11px] text-ink-50 mt-0.5">
          1 位主持人 · {perspectives.length} 位分析视角 · {judgeState ? '1 位裁判' : '0 位裁判'}
        </div>
      </div>

      {/* 我（主持人） */}
      <div>
        <div className="text-[11px] text-ink-50 mb-2 px-1 font-hand tracking-wider">主持人</div>
        <div className="flex items-center gap-3 p-2.5 bg-sticky-cream/60 rounded-hd-md border-2 border-marker-gold/50 hd-filter">
          <HandDrawnAvatar content="👤" size="md" color="gold" crown />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-bold text-ink-300">我</div>
            <div className="text-[11px] text-ink-50 truncate">主持人 · 决策困境提出者</div>
          </div>
          <HandDrawnBadge variant="gold" size="sm" dot>主持</HandDrawnBadge>
        </div>
      </div>

      {/* 分析视角 */}
      {perspectives.length > 0 && (
        <div>
          <div className="text-[11px] text-ink-50 mb-2 px-1 font-hand tracking-wider">
            分析视角 ({perspectives.length})
          </div>
          <div className="space-y-2">
            {perspectives.map((p, i) => {
              const state = agentStates.find(a => a.id === p.id)
              const status = state?.status || 'idle'
              const statusInfo = STATUS_LABELS[status] || STATUS_LABELS.idle

              return (
                <div
                  key={p.id}
                  className="flex items-center gap-3 p-2 bg-paper-100/60 rounded-hd-sm border border-divider/60
                    hover:bg-paper-200/60 transition-colors"
                >
                  <HandDrawnAvatar
                    content={p.name.charAt(0)}
                    size="sm"
                    color={AVATAR_COLORS[i % AVATAR_COLORS.length]}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-ink-300 truncate">{p.name}</div>
                    {p.stance && (
                      <div className="text-[10px] text-ink-50 truncate">{p.stance}</div>
                    )}
                  </div>
                  <HandDrawnBadge variant={statusInfo.variant} size="sm" dot>
                    {statusInfo.label}
                  </HandDrawnBadge>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 裁判 */}
      {judgeState && (
        <div>
          <div className="text-[11px] text-ink-50 mb-2 px-1 font-hand tracking-wider">裁判</div>
          <div className="flex items-center gap-3 p-2 bg-sticky-white/60 rounded-hd-sm border-2 border-divider hd-filter tilt-right">
            <HandDrawnAvatar content="⚖️" size="sm" color="purple" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-ink-300">裁判 Agent</div>
              <div className="text-[10px] text-ink-50">中立客观 · 综合判断</div>
            </div>
            <HandDrawnBadge
              variant={STATUS_LABELS[judgeState.status]?.variant || 'default'}
              size="sm"
              dot
            >
              {STATUS_LABELS[judgeState.status]?.label || '等待中'}
            </HandDrawnBadge>
          </div>
        </div>
      )}

      {/* 空态 */}
      {perspectives.length === 0 && !judgeState && (
        <div className="text-center py-6 text-ink-50">
          <p className="text-2xl mb-2">🤔</p>
          <p className="text-xs">视角生成中...</p>
        </div>
      )}
    </div>
  )
}
