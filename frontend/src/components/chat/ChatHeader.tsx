/** 微信风格群聊顶部栏 */
import { useNavigate } from 'react-router-dom'

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

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-[#EDEDED] border-b border-gray-300">
      <div className="flex items-center h-12 px-4 max-w-2xl mx-auto">
        {/* 返回按钮 */}
        <button
          onClick={() => navigate('/')}
          className="text-gray-700 hover:text-gray-900 mr-3 shrink-0"
          aria-label="返回"
        >
          <svg width="12" height="20" viewBox="0 0 12 20" fill="none">
            <path d="M10 2L2 10L10 18" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>

        {/* 标题区域 */}
        <div className="flex-1 text-center min-w-0">
          <h1 className="text-base font-semibold text-gray-900 truncate">
            {title}
          </h1>
          <p className="text-xs text-gray-500 truncate">
            {phase && PHASE_LABELS[phase]
              ? PHASE_LABELS[phase]
              : `${memberCount}人群聊`
            }
          </p>
        </div>

        {/* 右侧占位——保持标题居中 */}
        <div className="w-[28px] shrink-0" />
      </div>
    </div>
  )
}
