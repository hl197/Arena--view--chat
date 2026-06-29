/** 涟漪扩散入场动效 — 手绘手账风
 *
 *  阶段 1：中心出现（约 0.8s）— 用户头像从中心放大出现，带皇冠 👑
 *  阶段 2：涟漪扩散（持续）— 每个 Agent 头像从中心荡漾到圆周位置
 *  阶段 3：群聊展开（约 0.8s）— 整体缩小上移淡出，群聊界面展开
 */

import { useState, useEffect, useMemo } from 'react'
import HandDrawnAvatar from '../ui/HandDrawnAvatar'

interface RippleAgent {
  id: string
  name: string
  avatar?: string
}

interface RippleEntranceProps {
  agents: RippleAgent[]      // 已出现的 Agent 列表
  status: string             // 当前讨论状态
  question?: string          // 用户提出的问题
}

const AVATAR_COLORS: Array<'red' | 'blue' | 'green' | 'yellow' | 'purple' | 'pink' | 'cyan'> = [
  'blue', 'pink', 'green', 'yellow', 'purple', 'red', 'cyan',
]

function getAvatarContent(name: string): string {
  // 取名字第一个字符作为头像内容
  return name.charAt(0) || '🤖'
}

export default function RippleEntrance({ agents, status, question }: RippleEntranceProps) {
  const [phase, setPhase] = useState<'center' | 'ripple' | 'expand'>('center')
  const [showRings, setShowRings] = useState(false)

  // 阶段 1 → 阶段 2
  useEffect(() => {
    const t = setTimeout(() => {
      setPhase('ripple')
      setShowRings(true)
    }, 800)
    return () => clearTimeout(t)
  }, [])

  // 状态变为研究/辩论后，触发阶段 3（群聊展开）
  useEffect(() => {
    if (phase === 'expand') return
    if (['researching', 'debating', 'synthesizing', 'completed'].includes(status)) {
      // 给最后一个 agent 一点时间出场
      const t = setTimeout(() => setPhase('expand'), 600)
      return () => clearTimeout(t)
    }
  }, [status, phase])

  // 计算每个 agent 的圆周位置
  const positions = useMemo(() => {
    const count = Math.max(agents.length, 1)
    const radius = 130 // px
    return agents.map((agent, i) => {
      // 从顶部开始，顺时针分布
      const angle = (i / count) * Math.PI * 2 - Math.PI / 2
      const x = Math.cos(angle) * radius
      const y = Math.sin(angle) * radius
      return { agent, x, y, delay: i * 0.5, colorIdx: i % AVATAR_COLORS.length }
    })
  }, [agents])

  const isExpanding = phase === 'expand'

  return (
    <div
      className={`absolute inset-0 z-40 flex items-center justify-center paper-bg pointer-events-none
        transition-opacity duration-500
        ${isExpanding ? 'opacity-0' : 'opacity-100'}
      `}
      style={{
        transform: isExpanding ? 'translateY(-20%) scale(0.8)' : 'translateY(0) scale(1)',
        transition: 'opacity 0.6s ease-in-out, transform 0.6s ease-in-out',
      }}
    >
      {/* 涟漪环 */}
      <div className="absolute flex items-center justify-center">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className={`absolute rounded-full border-2 border-dashed
              transition-all duration-[1200ms] ease-out
              ${showRings ? 'opacity-40 border-marker-blue/50' : 'opacity-0 border-marker-blue/0'}
            `}
            style={{
              width: showRings ? 80 + i * 80 : 0,
              height: showRings ? 80 + i * 80 : 0,
              transitionDelay: `${i * 150}ms`,
              filter: 'url(#hand-drawn-light)',
            }}
          />
        ))}
      </div>

      {/* 装饰性纸胶带 */}
      <div
        className={`absolute top-1/4 left-1/4 w-20 h-4 washi-tape washi-blue rotate-12 opacity-60
          transition-all duration-700
          ${showRings ? 'opacity-60' : 'opacity-0'}
        `}
        style={{ transitionDelay: '400ms' }}
      />
      <div
        className={`absolute bottom-1/3 right-1/4 w-16 h-4 washi-tape washi-pink -rotate-6 opacity-60
          transition-all duration-700
          ${showRings ? 'opacity-60' : 'opacity-0'}
        `}
        style={{ transitionDelay: '600ms' }}
      />

      {/* 问题文字 */}
      {question && phase === 'ripple' && (
        <div
          className="absolute top-[calc(50%-220px)] max-w-md text-center px-6"
          style={{
            animation: 'fadeSlideDown 0.6s ease-out forwards',
          }}
        >
          <div className="text-[11px] text-ink-50 mb-1 font-hand tracking-wider">你的问题</div>
          <div className="text-sm text-ink-300 font-medium bg-sticky-cream/80 px-4 py-2 rounded-hd-md shadow-sticky hd-filter tilt-right">
            {question}
          </div>
        </div>
      )}

      {/* 中心用户头像（带皇冠） */}
      <div
        className="absolute z-10 flex flex-col items-center"
        style={{
          animation: phase === 'center'
            ? 'popIn 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) forwards'
            : 'none',
          transform: phase === 'center' ? 'scale(0)' : 'scale(1)',
        }}
      >
        <HandDrawnAvatar
          content="👤"
          size="xl"
          crown
          color="gold"
        />
        <span className="mt-2 text-xs text-ink-200 font-hand font-bold">我（主持人）</span>
      </div>

      {/* Agent 头像涟漪扩散 */}
      <div className="absolute" style={{ width: 0, height: 0 }}>
        {positions.map(({ agent, x, y, delay, colorIdx }, i) => (
          <div
            key={agent.id}
            className="absolute flex flex-col items-center"
            style={{
              left: '50%',
              top: '50%',
              transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`,
              animation: `rippleOut 0.7s cubic-bezier(0.34, 1.56, 0.64, 1) ${delay}s both`,
            }}
          >
            <HandDrawnAvatar
              content={agent.avatar ? '' : getAvatarContent(agent.name)}
              size="md"
              color={AVATAR_COLORS[colorIdx]}
              className={agent.avatar ? '' : ''}
            />
            <span
              className="mt-1 text-[10px] text-ink-100 font-medium whitespace-nowrap max-w-20 truncate
                bg-paper-100/80 px-1.5 py-0.5 rounded-full"
            >
              {agent.name}
            </span>
          </div>
        ))}
      </div>

      {/* 状态文字 */}
      <div
        className={`absolute bottom-[calc(50%-200px)] text-center transition-opacity duration-500
          ${phase === 'ripple' ? 'opacity-100' : 'opacity-0'}
        `}
        style={{ transitionDelay: phase === 'ripple' ? '300ms' : '0ms' }}
      >
        <div className="text-sm text-ink-200 font-hand mb-1">
          {status === 'generating' ? '正在生成分析视角...' : '准备就绪！'}
        </div>
        <div className="flex gap-1 justify-center">
          <span
            className="w-2 h-2 rounded-full bg-marker-blue"
            style={{ animation: 'bounce 0.6s infinite', animationDelay: '0ms' }}
          />
          <span
            className="w-2 h-2 rounded-full bg-marker-purple"
            style={{ animation: 'bounce 0.6s infinite', animationDelay: '150ms' }}
          />
          <span
            className="w-2 h-2 rounded-full bg-marker-green"
            style={{ animation: 'bounce 0.6s infinite', animationDelay: '300ms' }}
          />
        </div>
      </div>
    </div>
  )
}
