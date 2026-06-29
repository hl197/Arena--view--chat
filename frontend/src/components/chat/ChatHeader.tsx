/** 手绘风格群聊顶部栏 */
import { useNavigate } from 'react-router-dom'
import { useUIStore } from '../../store/uiStore'

interface ChatHeaderProps {
  title: string
  memberCount: number
  phase?: string
}

const PHASE_LABELS: Record<string, string> = {
  perspectives: '正在生成视角...',
  research: '视角独立研究中...',
  debate: '交叉辩论中...',
  synthesis: '裁判合成决策地图...',
}

export default function ChatHeader({ title, memberCount, phase }: ChatHeaderProps) {
  const navigate = useNavigate()
  const { openRightPanel, toggleSidebar, sidebarCollapsed } = useUIStore()

  return (
    <div className="bg-paper-100/90 backdrop-blur border-b-2 border-divider">
      <div className="flex items-center h-14 px-4">
        {/* 折叠侧边栏按钮 */}
        <button
          onClick={toggleSidebar}
          className="p-2 mr-1 hover:bg-paper-200 rounded-hd-sm text-ink-200 transition-colors"
          title={sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
        >
          {sidebarCollapsed ? '→' : '←'}
        </button>

        {/* 返回首页 */}
        <button
          onClick={() => navigate('/')}
          className="p-2 hover:bg-paper-200 rounded-hd-sm text-ink-200 transition-colors mr-2"
          title="返回首页"
        >
          🏠
        </button>

        {/* 标题区域 */}
        <div className="flex-1 text-center min-w-0">
          <h1 className="text-base font-bold text-ink-300 truncate font-hand tracking-wide">
            {title}
          </h1>
          <p className="text-xs text-ink-50 truncate">
            {phase && PHASE_LABELS[phase]
              ? PHASE_LABELS[phase]
              : `${memberCount} 人讨论中`
            }
          </p>
        </div>

        {/* 右侧操作 */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => openRightPanel('members')}
            className="p-2 hover:bg-paper-200 rounded-hd-sm text-ink-200 transition-colors"
            title="成员"
          >
            👥
          </button>
          <button
            onClick={() => openRightPanel('decision-map')}
            className="p-2 hover:bg-paper-200 rounded-hd-sm text-ink-200 transition-colors"
            title="决策地图"
          >
            🗺️
          </button>
        </div>
      </div>
    </div>
  )
}
