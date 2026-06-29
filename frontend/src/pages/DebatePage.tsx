/** 群聊辩论页面 — 手绘手账风两栏布局 */
import { useEffect, useRef, useCallback, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useDebateStore, nextMsgId, AVATAR_MAP } from '../store/debateStore'
import { useUIStore } from '../store/uiStore'
import { useSSE } from '../hooks/useSSE'
import { post } from '../api/client'
import HistorySidebar from '../components/sidebar/HistorySidebar'
import ChatHeader from '../components/chat/ChatHeader'
import AgentStatusBar from '../components/chat/AgentStatusBar'
import MessageBubble from '../components/chat/MessageBubble'
import ChatInput from '../components/chat/ChatInput'
import TypingIndicator from '../components/chat/TypingIndicator'
import TimeStamp from '../components/chat/TimeStamp'
import RippleEntrance from '../components/chat/RippleEntrance'
import HandDrawnButton from '../components/ui/HandDrawnButton'
import MemberPanel from '../components/panel/MemberPanel'
import DecisionMapPanel from '../components/panel/DecisionMapPanel'
import type { SSEEvent, ChatMessage } from '../api/types'
import type { AgentStateItem } from '../store/debateStore'

function needsTimeStamp(prev: ChatMessage | undefined, curr: ChatMessage): boolean {
  if (!prev) return true
  return curr.timestamp - prev.timestamp > 2 * 60 * 1000
}

function isConsecutive(prev: ChatMessage | undefined, curr: ChatMessage): boolean {
  if (!prev) return false
  return (
    prev.senderId === curr.senderId &&
    prev.type === curr.type &&
    curr.timestamp - prev.timestamp < 60_000
  )
}

export default function DebatePage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const store = useDebateStore()
  const { sidebarWidth, sidebarCollapsed, rightPanelOpen, rightPanelTab, setRightPanelTab, openRightPanel } = useUIStore()
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [isDragging, setIsDragging] = useState(false)

  // 消息延迟队列（ref 避免闭包问题）
  const queueRef = useRef<Array<() => void>>([])
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const processingRef = useRef(false)

  // 发言 chunk 累积缓冲
  const speechBufferRef = useRef<Map<string, string>>(new Map())

  const processNext = useCallback(() => {
    if (queueRef.current.length === 0) {
      processingRef.current = false
      timerRef.current = null
      return
    }
    processingRef.current = true
    const fn = queueRef.current.shift()!
    fn()
    if (queueRef.current.length > 0) {
      timerRef.current = setTimeout(processNext, 2500)
    } else {
      processingRef.current = false
      timerRef.current = null
    }
  }, [])

  /** 发消息：所有消息排队依次显示 */
  const addMsg = useCallback((msg: ChatMessage) => {
    if (msg.type === 'user') {
      store.addMessage(msg)
      return
    }
    queueRef.current.push(() => store.addMessage(msg))
    if (!processingRef.current) {
      timerRef.current = setTimeout(processNext, 600)
    }
  }, [store, processNext])

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => { scrollToBottom() }, [store.messages, store.typingNames, scrollToBottom])

  // 清理
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  // 拖拽调整侧边栏宽度
  const dragStartXRef = useRef(0)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragStartXRef.current = e.clientX
    setIsDragging(true)
  }, [])

  useEffect(() => {
    if (!isDragging) return
    const startX = dragStartXRef.current
    const startWidth = sidebarWidth

    const handleMouseMove = (e: MouseEvent) => {
      const diff = e.clientX - startX
      const newWidth = Math.max(240, Math.min(480, startWidth + diff))
      useUIStore.getState().setSidebarWidth(newWidth)
    }
    const handleMouseUp = () => {
      setIsDragging(false)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isDragging, sidebarWidth])

  // SSE → ChatMessage + AgentState
  const handleSSEEvent = useCallback((event: SSEEvent) => {
    const now = Date.now()
    const mkSys = (content: string): ChatMessage => ({
      id: nextMsgId(), senderId: 'system', senderName: '', content, timestamp: now, type: 'system',
    })

    switch (event.type) {
      case 'phase': {
        const phase = event.phase as string
        store.setPhase(phase)
        store.setStatus(
          phase === 'perspectives' ? 'generating'
          : phase === 'discussion' ? 'debating'
          : phase === 'research' ? 'researching'
          : phase === 'debate' ? 'debating'
          : phase === 'synthesis' ? 'synthesizing'
          : store.status
        )
        addMsg(mkSys(
          phase === 'perspectives' ? '📋 正在生成分析视角...'
          : phase === 'discussion' ? '💬 群聊讨论开始！大家按顺序发言'
          : phase === 'research' ? '📚 各视角开始独立研究，稍等片刻...'
          : phase === 'debate' ? '⚔️ 交叉辩论开始！大家可以互相质询了'
          : phase === 'synthesis' ? '🧠 裁判开始梳理所有观点，生成决策地图...'
          : phase
        ))
        if (phase === 'synthesis') store.setJudgeState('thinking')
        break
      }

      case 'perspective_ready': {
        const pName = (event.name || event.perspective_name || '') as string
        const pId = (event.id || event.perspective_id || '') as string
        store.addPerspective({ id: pId, name: pName, stance: (event.stance || '') as string })
        store.setAgentStatus(pName, 'idle')
        break
      }

      case 'self_intro': {
        const senderName = (event.perspective_name || '') as string
        const senderId = (event.perspective_id || '') as string
        const text = (event.text || '') as string
        if (text.trim()) {
          addMsg({
            id: nextMsgId(), senderId, senderName,
            avatar: AVATAR_MAP[senderId],
            content: text, timestamp: now, type: 'agent',
          })
        }
        store.setAgentStatus(senderName, 'idle')
        break
      }

      case 'agent_status': {
        const agentName = (event.perspective_name || '') as string
        const rawStatus = (event.status || '') as string
        store.setAgentStatus(agentName, rawStatus)
        // composing 也显示"发言中"，让用户看到谁在说话
        if (['searching', 'researching', 'debating', 'composing'].includes(rawStatus)) {
          const names = store.typingNames
          if (!names.includes(agentName)) {
            store.setTypingNames([...names, agentName])
          }
        } else {
          store.setTypingNames(store.typingNames.filter(n => n !== agentName))
        }
        break
      }

      case 'argument_chunk': {
        const senderName = (event.perspective_name || 'Agent') as string
        const perspective = store.perspectives.find(p => p.name === senderName)
        const senderId = perspective?.id || 'unknown'
        const text = (event.text || event.summary || '') as string
        if (text.trim()) {
          addMsg({
            id: nextMsgId(), senderId, senderName,
            avatar: AVATAR_MAP[senderId],
            content: text, timestamp: now, type: 'agent',
          })
        }
        break
      }

      case 'research_chunk': {
        const senderName = (event.perspective_name || 'Agent') as string
        const perspective = store.perspectives.find(p => p.name === senderName)
        const senderId = perspective?.id || 'unknown'
        const text = (event.text || '') as string
        const isFinal = event.is_final as boolean

        if (text.trim()) {
          const lastMsg = store.messages[store.messages.length - 1]
          if (isFinal === false && lastMsg && lastMsg.senderId === senderId && lastMsg.type === 'agent') {
            store.appendToLastMessage(text)
          } else {
            addMsg({
              id: nextMsgId(), senderId, senderName,
              avatar: AVATAR_MAP[senderId],
              content: text, timestamp: now, type: 'agent',
            })
          }
        }

        if (isFinal) {
          store.setTypingNames(store.typingNames.filter(n => n !== senderName))
          store.setAgentStatus(senderName, 'done')
        }
        break
      }

      case 'argument_complete': {
        const agentName = (event.perspective_name || '') as string
        store.setTypingNames(store.typingNames.filter(n => n !== agentName))
        store.setAgentStatus(agentName, 'done')
        addMsg(mkSys(`✅ ${agentName} 已完成论证`))
        break
      }

      case 'round_start': {
        const rn = event.round_number as number
        const desc = (event.description || `第${rn}轮讨论`) as string
        addMsg(mkSys(`🔄 ${desc}`))
        break
      }

      case 'speech_chunk': {
        const senderName = (event.perspective_name || 'Agent') as string
        const perspective = store.perspectives.find(p => p.name === senderName)
        const senderId = perspective?.id || (event.perspective_id as string) || 'unknown'
        const text = (event.text || '') as string
        const isFinal = event.is_final as boolean

        if (text.trim()) {
          const buffer = speechBufferRef.current
          const accumulated = (buffer.get(senderId) || '') + text
          buffer.set(senderId, accumulated)

          if (isFinal) {
            const fullText = buffer.get(senderId) || ''
            buffer.delete(senderId)
            addMsg({
              id: nextMsgId(), senderId, senderName,
              avatar: AVATAR_MAP[senderId],
              content: fullText, timestamp: now, type: 'agent',
            })
            // 只移除当前发言者，不清空全员（并行场景其他人可能还在搜）
            store.setTypingNames(store.typingNames.filter(n => n !== senderName))
            store.setAgentStatus(senderName, 'done')
          } else {
            store.setAgentStatus(senderName, 'composing')
            store.setTypingNames([senderName])
          }
        }
        break
      }

      case 'speech_end': {
        const senderName = (event.perspective_name || '') as string
        const perspective = store.perspectives.find(p => p.name === senderName)
        const senderId = perspective?.id || (event.perspective_id as string) || 'unknown'

        const buffer = speechBufferRef.current
        const remaining = buffer.get(senderId)
        if (remaining) {
          buffer.delete(senderId)
          addMsg({
            id: nextMsgId(), senderId, senderName,
            avatar: AVATAR_MAP[senderId],
            content: remaining, timestamp: now, type: 'agent',
          })
        }

        store.setAgentStatus(senderName, 'done')
        store.setTypingNames(store.typingNames.filter(n => n !== senderName))
        break
      }

      case 'round_end': {
        const rn = event.round_number as number
        addMsg(mkSys(`✅ 第${rn}轮讨论结束`))
        break
      }

      case 'debate_turn_start': {
        const challenger = (event.challenger_name || '') as string
        const defender = (event.defender_name || '') as string
        store.setAgentStatus(challenger, 'debating')
        store.setAgentStatus(defender, 'debating')
        store.setTypingNames([challenger])
        addMsg(mkSys(`⚔️ 第${event.round || '?'}轮 · ${challenger} 质疑 ${defender}`))
        break
      }

      case 'debate_chunk': {
        const senderName = (event.perspective_name || '') as string
        const perspective = store.perspectives.find(p => p.name === senderName)
        const senderId = perspective?.id || 'unknown'
        const text = (event.text || '') as string
        if (text.trim()) {
          addMsg({
            id: nextMsgId(), senderId, senderName,
            avatar: AVATAR_MAP[senderId],
            content: text, timestamp: now, type: 'agent',
          })
        }
        break
      }

      case 'debate_turn_end': {
        const challenger = (event.challenger_name || '') as string
        const defender = (event.defender_name || '') as string
        store.setAgentStatus(challenger, 'done')
        store.setAgentStatus(defender, 'done')
        store.setTypingNames([])
        if (event.judge_note) {
          store.setJudgeState('composing')
          addMsg({
            id: nextMsgId(), senderId: 'judge', senderName: '裁判',
            avatar: AVATAR_MAP['judge'],
            content: `📝 本轮小结：${event.judge_note}`,
            timestamp: now, type: 'judge',
          })
          store.setJudgeState('done')
        }
        break
      }

      case 'synthesis_start':
        store.setJudgeState('thinking')
        addMsg(mkSys('🧠 裁判开始综合分析大家的观点...'))
        break

      case 'self_reflection':
        store.setJudgeState('composing')
        {
          const iter = (event.iteration || 1) as number
          addMsg(mkSys(`🪞 裁判正在自我审查第 ${iter} 轮，检查偏见、遗漏和假共识...`))
        }
        break

      case 'decision_map_chunk':
        store.setDecisionMap((store.decisionMap || '') + (event.text || ''))
        // 辩论结束时自动打开决策地图面板
        if (event.is_final) {
          openRightPanel('decision-map')
        }
        break

      case 'tradeoff_update':
        addMsg({
          id: nextMsgId(), senderId: 'judge', senderName: '裁判',
          avatar: AVATAR_MAP['judge'],
          content: `📊 ${(event.text || event.summary || '') as string}`,
          timestamp: now, type: 'judge',
        })
        break

      case 'user_message':
        addMsg({
          id: nextMsgId(), senderId: 'other_user',
          senderName: (event.sender_name || '其他用户') as string,
          content: (event.content || '') as string,
          timestamp: now, type: 'user',
        })
        break

      case 'complete':
        store.setStatus('completed')
        store.setJudgeState('done')
        if (event.total_time_ms) store.setStats(store.totalTokens, event.total_time_ms as number)
        store.perspectives.forEach(p => store.setAgentStatus(p.name, 'done'))
        store.setTypingNames([])
        if (store.decisionMap) {
          addMsg({
            id: nextMsgId(), senderId: 'judge', senderName: '裁判',
            avatar: AVATAR_MAP['judge'],
            content: `📊 决策地图\n\n${store.decisionMap}`,
            timestamp: now, type: 'judge',
          })
          // 完成后自动打开决策地图
          openRightPanel('decision-map')
        }
        addMsg(mkSys(
          `🎉 讨论结束！总耗时 ${((event.total_time_ms as number || 0) / 1000).toFixed(1)}s`
        ))
        break

      case 'error':
        store.setError((event.message || event.data?.message || '未知错误') as string)
        addMsg(mkSys(`❌ 出错了：${event.message || '未知错误'}`))
        break
    }
  }, [store, addMsg, openRightPanel])

  // SSE 连接
  const { abort } = useSSE(
    sessionId ? `/api/debate/${sessionId}/stream` : null,
    handleSSEEvent,
    () => {},
    (err) => {
      store.setError(err)
      store.addMessage({
        id: nextMsgId(), senderId: 'system', senderName: '',
        content: `❌ 连接中断：${err}`, timestamp: Date.now(), type: 'system',
      })
    },
  )

  // 用户发消息
  const handleUserSend = useCallback(async (text: string) => {
    const now = Date.now()
    store.addMessage({
      id: nextMsgId(), senderId: 'user', senderName: '我',
      content: text, timestamp: now, type: 'user',
    })
    if (sessionId && store.status !== 'completed' && store.status !== 'error') {
      try { await post(`/debate/${sessionId}/message`, { content: text }) } catch { /* ok */ }
    }
  }, [sessionId, store.status])

  const handleCancel = () => { abort(); navigate('/') }

  const title = store.question
    ? `${store.question.slice(0, 20)}${store.question.length > 20 ? '...' : ''}`
    : '决策分析群聊'
  const memberCount = store.perspectives.length + 1

  const allAgents: AgentStateItem[] = [
    ...store.agentStates,
    ...(store.judgeState ? [store.judgeState] : []),
  ]

  const sidebarActualWidth = sidebarCollapsed ? 56 : sidebarWidth

  return (
    <div className="h-screen flex bg-paper-100 overflow-hidden">
      {/* 左侧：历史侧边栏 */}
      <div
        style={{ width: sidebarActualWidth }}
        className="h-full flex-shrink-0 transition-[width] duration-200"
      >
        <HistorySidebar
          activeSessionId={sessionId}
          onSelect={(id) => navigate(`/debate/${id}`)}
        />
      </div>

      {/* 拖拽分割线 */}
      {!sidebarCollapsed && (
        <div
          className={`w-1.5 h-full cursor-col-resize bg-divider/30 hover:bg-marker-blue/40 transition-colors ${
            isDragging ? 'bg-marker-blue/60' : ''
          }`}
          onMouseDown={handleMouseDown}
        />
      )}

      {/* 右侧：群聊主区域 */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        <ChatHeader title={title} memberCount={memberCount} phase={store.phase} />

        {/* Agent 状态栏 */}
        <AgentStatusBar agents={allAgents} phase={store.phase} />

        {/* 消息区域 */}
        <div className="flex-1 relative overflow-hidden">
          {/* 涟漪入场动效（generating 阶段覆盖显示） */}
          {store.status === 'generating' && store.perspectives.length >= 0 && (
            <RippleEntrance
              agents={store.perspectives.map(p => ({
                id: p.id,
                name: p.name,
                avatar: AVATAR_MAP[p.id],
              }))}
              status={store.status}
              question={store.question}
            />
          )}

          <div
            ref={scrollRef}
            className="h-full overflow-y-auto paper-bg hd-scrollbar"
            style={{ scrollBehavior: 'smooth' }}
          >
            <div className="max-w-3xl mx-auto py-4">
              {store.messages.length === 0 && store.status === 'idle' && (
                <div className="flex justify-center mt-8">
                  <span className="text-xs text-ink-50 bg-paper-200/60 border border-dashed border-divider rounded-full px-4 py-1.5 hd-filter">
                    等待讨论开始...
                  </span>
                </div>
              )}

              {store.messages.map((msg, i) => {
                const prev = i > 0 ? store.messages[i - 1] : undefined
                return (
                  <div key={msg.id}>
                    {needsTimeStamp(prev, msg) && <TimeStamp time={msg.timestamp} />}
                    <MessageBubble message={msg} isConsecutive={isConsecutive(prev, msg)} />
                  </div>
                )
              })}

              {store.typingNames.length > 0 && store.status !== 'completed' && (
                <TypingIndicator names={store.typingNames} />
              )}

              {store.status === 'completed' && (
                <div className="flex justify-center gap-3 my-6 flex-wrap">
                  <HandDrawnButton
                    variant="secondary"
                    size="md"
                    onClick={() => { setRightPanelTab('decision-map'); openRightPanel('decision-map') }}
                  >
                    📊 查看决策地图
                  </HandDrawnButton>
                  <HandDrawnButton
                    variant="primary"
                    size="md"
                    onClick={() => navigate('/')}
                    tilt="right"
                  >
                    ✏️ 发起新讨论
                  </HandDrawnButton>
                </div>
              )}

              {store.status === 'error' && (
                <div className="flex flex-col items-center gap-3 my-8">
                  <span className="text-4xl">😞</span>
                  <p className="text-sm text-ink-50">{store.error || '出了点问题'}</p>
                  <HandDrawnButton variant="primary" onClick={() => navigate('/')}>
                    返回首页重试
                  </HandDrawnButton>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          </div>
        </div>

        <ChatInput
          onSend={handleUserSend}
          disabled={store.status === 'completed' || store.status === 'error'}
          placeholder={
            store.status === 'completed' ? '讨论已结束'
            : store.status === 'error' ? '讨论出错'
            : '说说你的想法...'
          }
        />

        {/* 右下角浮动操作按钮 */}
        {store.status !== 'completed' && store.status !== 'error' && store.status !== 'idle' && (
          <div className="absolute bottom-20 right-4">
            <button
              onClick={handleCancel}
              className="bg-sticky-white/90 border-2 border-divider text-ink-200 hover:text-marker-red hover:border-marker-red px-3 py-1.5 rounded-full text-xs shadow-sticky transition-colors hd-filter"
            >
              结束讨论
            </button>
          </div>
        )}

        {/* 右侧面板占位（阶段5实现） */}
        {rightPanelOpen && (
          <div className="absolute top-0 right-0 h-full w-80 bg-paper-100 border-l-2 border-divider shadow-lg z-30 animate-[slideInRight_0.3s_ease-out]">
            {/* Tab 头部 */}
            <div className="flex border-b-2 border-divider">
              <button
                className={`flex-1 py-3 text-sm font-medium transition-colors ${
                  rightPanelTab === 'members'
                    ? 'text-marker-blue border-b-2 border-marker-blue'
                    : 'text-ink-100 hover:text-ink-300'
                }`}
                onClick={() => setRightPanelTab('members')}
              >
                👥 成员
              </button>
              <button
                className={`flex-1 py-3 text-sm font-medium transition-colors ${
                  rightPanelTab === 'decision-map'
                    ? 'text-marker-blue border-b-2 border-marker-blue'
                    : 'text-ink-100 hover:text-ink-300'
                }`}
                onClick={() => setRightPanelTab('decision-map')}
              >
                🗺️ 决策地图
              </button>
              <button
                onClick={() => useUIStore.getState().closeRightPanel()}
                className="px-3 text-ink-50 hover:text-ink-300"
              >
                ✕
              </button>
            </div>

            {/* 面板内容 */}
            <div className="p-4 overflow-y-auto h-[calc(100%-48px)] hd-scrollbar">
              {rightPanelTab === 'members' ? (
                <MemberPanel
                  perspectives={store.perspectives}
                  agentStates={store.agentStates}
                  judgeState={store.judgeState}
                />
              ) : (
                <DecisionMapPanel content={store.decisionMap} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
