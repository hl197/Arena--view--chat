/** 群聊辩论页面 — 手绘手账风两栏布局 */
import { useEffect, useRef, useCallback, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useDebateStore, nextMsgId, AVATAR_MAP } from '../store/debateStore'
import { useUIStore } from '../store/uiStore'
import { useSSE } from '../hooks/useSSE'
import { get, post } from '../api/client'
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
  const [loadingHistory, setLoadingHistory] = useState(false)  // 加载历史消息时的提示
  const [blockedReminder, setBlockedReminder] = useState(false)  // 生成中点击被拦截的提醒

  // 是否正在生成决策（禁止切换页面）
  const isGenerating = store.status === 'generating' || store.status === 'researching' || store.status === 'debating' || store.status === 'synthesizing'

  // 浏览器关闭/刷新拦截
  useEffect(() => {
    if (!isGenerating) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = '决策正在生成中，离开页面将丢失进度'
      return '决策正在生成中，离开页面将丢失进度'
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [isGenerating])

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
    try {
      fn()
    } catch (e) {
      console.error('消息队列处理失败:', e)
      // 单条消息失败不影响后续消息
    }
    if (queueRef.current.length > 0) {
      timerRef.current = setTimeout(processNext, 2000)
    } else {
      processingRef.current = false
      timerRef.current = null
    }
  }, [])

  /** 发消息：所有消息排队依次显示 */
  const addMsg = useCallback((msg: ChatMessage) => {
    const s = useDebateStore.getState()
    if (msg.type === 'user') {
      s.addMessage(msg)
      return
    }
    queueRef.current.push(() => s.addMessage(msg))
    if (!processingRef.current) {
      timerRef.current = setTimeout(processNext, 200)  // 首条快速响应
    }
  }, [processNext])

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

  // 监听 sessionId 变化：点击侧边栏切换历史时，React Router 不会重新挂载组件，
  // 需要手动重置 store + 清空历史加载标记，否则页面不刷新
  const prevSessionIdRef = useRef(sessionId)
  useEffect(() => {
    // 初始挂载时 prev === 当前值，跳过（避免清掉 HomePage 设置的 generating 状态）
    if (prevSessionIdRef.current === sessionId) return
    prevSessionIdRef.current = sessionId

    // 清理旧会话的队列和缓冲，防止旧数据污染新会话
    queueRef.current = []
    speechBufferRef.current.clear()
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
    processingRef.current = false

    // 重置历史加载标记，允许 loadHistoryResult 再次执行
    historyLoadedRef.current = false
    setLoadingHistory(false)
    // 清空旧会话的数据
    store.reset()
    if (sessionId) {
      store.setSessionId(sessionId)
    }
  }, [sessionId])  // 只依赖 sessionId，不依赖整个 store 对象

  // 回连已有会话：如果 store 为空（不是从 HomePage 新建的），先从 REST 加载当前状态
  useEffect(() => {
    if (!sessionId) return
    // 用 getState() 读取即时状态，不把 store 状态放依赖数组避免循环触发
    const state = useDebateStore.getState()
    if (state.question && state.status !== 'idle') return
    if (state.messages.length > 0) return
    loadHistoryResult(sessionId)
  }, [sessionId])  // loadHistoryResult 是稳定引用，不需要放依赖

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
  // 历史回放：是否已从 API 加载过
  const historyLoadedRef = useRef(false)

  /** 从 REST API 加载辩论结果——兼容进行中和已完成的辩论
   *  使用 getState() 而非响应式 store，避免 callback 每次渲染都变化 */
  const loadHistoryResult = useCallback(async (sid: string) => {
    if (historyLoadedRef.current) return
    historyLoadedRef.current = true
    setLoadingHistory(true)

    try {
      const result = await get<{
        session_id: string
        question: string
        status: string
        perspectives: Array<{ id: string; name: string; stance: string }>
        arguments: Record<string, string>
        debate_transcript: Array<{
          round: number
          speaker: string
          speaker_id: string
          text: string
        }>
        decision_map: string
        total_tokens: number
        total_time_ms: number
      }>(`/debate/${sid}/result`)

      const s = useDebateStore.getState()
      const ui = useUIStore.getState()
      s.setSessionId(result.session_id)
      s.setQuestion(result.question)

      // 根据实际状态设置（进行中 / 已完成）
      // 关键：perspectives 为空 + running = 新辩论刚启动，不要设状态，
      // 让 SSE 的 phase 事件来控制，避免竞争导致"卡在入场动画"
      const isRunning = result.status === 'running'
      const isEmpty = result.perspectives.length === 0
      if (!isEmpty) {
        s.setStatus(isRunning ? 'debating' : 'completed')
        s.setPhase(isRunning ? 'discussion' : 'synthesis')
      }

      // 填充视角
      for (const p of result.perspectives) {
        s.addPerspective(p)
        s.setAgentStatus(p.name, isRunning ? 'idle' : 'done')
      }

      // 将对话记录转成 ChatMessage（历史消息直接 addMessage，不走队列）
      const baseTime = Date.now()
      let msgIndex = 0
      for (const entry of result.debate_transcript) {
        const isJudge = entry.speaker_id === 'judge'
        s.addMessage({
          id: `hist_${msgIndex++}`,
          senderId: entry.speaker_id,
          senderName: entry.speaker,
          avatar: isJudge ? '/avatars/judge.png' : AVATAR_MAP[entry.speaker_id],
          content: entry.text,
          timestamp: baseTime + msgIndex * 60000,
          type: isJudge ? 'judge' : 'agent',
        })
      }

      // 决策地图（仅在完成时展示）
      if (result.decision_map && !isRunning) {
        s.setDecisionMap(result.decision_map)
        s.addMessage({
          id: `hist_judge`,
          senderId: 'judge',
          senderName: '裁判',
          content: result.decision_map,
          timestamp: baseTime + (result.debate_transcript.length + 1) * 60000,
          type: 'judge',
        })
        ui.openRightPanel('decision-map')
      }

      s.setStats(result.total_tokens, result.total_time_ms)
    } catch {
      useDebateStore.getState().setError('加载历史记录失败')
    } finally {
      setLoadingHistory(false)
    }
  }, [])  // 稳定引用，永不变化

  const handleSSEEvent = useCallback((event: SSEEvent) => {
    const now = Date.now()
    const s = store
    const mkSys = (content: string): ChatMessage => ({
      id: nextMsgId(), senderId: 'system', senderName: '', content, timestamp: now, type: 'system',
    })

    switch (event.type) {
      case 'phase': {
        const phase = event.phase as string
        s.setPhase(phase)
        s.setStatus(
          phase === 'perspectives' ? 'generating'
          : phase === 'discussion' ? 'debating'
          : phase === 'research' ? 'researching'
          : phase === 'debate' ? 'debating'
          : phase === 'synthesis' ? 'synthesizing'
          : s.status
        )
        addMsg(mkSys(
          phase === 'perspectives' ? '📋 正在生成分析视角...'
          : phase === 'discussion' ? '💬 群聊讨论开始！大家按顺序发言'
          : phase === 'research' ? '📚 各视角开始独立研究，稍等片刻...'
          : phase === 'debate' ? '⚔️ 交叉辩论开始！大家可以互相质询了'
          : phase === 'synthesis' ? '🧠 裁判开始梳理所有观点，生成决策地图...'
          : phase
        ))
        if (phase === 'synthesis') s.setJudgeState('thinking')
        break
      }

      case 'perspective_ready': {
        const pName = (event.name || event.perspective_name || '') as string
        const pId = (event.id || event.perspective_id || '') as string
        s.addPerspective({ id: pId, name: pName, stance: (event.stance || '') as string })
        s.setAgentStatus(pName, 'idle')
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
        s.setAgentStatus(senderName, 'idle')
        break
      }

      case 'agent_status': {
        const agentName = (event.perspective_name || '') as string
        const rawStatus = (event.status || '') as string
        s.setAgentStatus(agentName, rawStatus)
        // composing 也显示"发言中"，让用户看到谁在说话
        if (['searching', 'researching', 'debating', 'composing'].includes(rawStatus)) {
          const names = s.typingNames
          if (!names.includes(agentName)) {
            s.setTypingNames([...names, agentName])
          }
        } else {
          s.setTypingNames(s.typingNames.filter(n => n !== agentName))
        }
        break
      }

      case 'argument_chunk': {
        const senderName = (event.perspective_name || 'Agent') as string
        const perspective = s.perspectives.find(p => p.name === senderName)
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
        const perspective = s.perspectives.find(p => p.name === senderName)
        const senderId = perspective?.id || 'unknown'
        const text = (event.text || '') as string
        const isFinal = event.is_final as boolean

        if (text.trim()) {
          const lastMsg = s.messages[s.messages.length - 1]
          if (isFinal === false && lastMsg && lastMsg.senderId === senderId && lastMsg.type === 'agent') {
            s.appendToLastMessage(text)
          } else {
            addMsg({
              id: nextMsgId(), senderId, senderName,
              avatar: AVATAR_MAP[senderId],
              content: text, timestamp: now, type: 'agent',
            })
          }
        }

        if (isFinal) {
          s.setTypingNames(s.typingNames.filter(n => n !== senderName))
          s.setAgentStatus(senderName, 'done')
        }
        break
      }

      case 'argument_complete': {
        const agentName = (event.perspective_name || '') as string
        s.setTypingNames(s.typingNames.filter(n => n !== agentName))
        s.setAgentStatus(agentName, 'done')
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
        // 优先用 event.perspective_id（后端保证发送），避免 store 未就绪时退化为 'unknown'
        const senderId = (event.perspective_id as string) || (() => {
          const senderName = (event.perspective_name || 'Agent') as string
          const p = s.perspectives.find(pp => pp.name === senderName)
          return p?.id || 'unknown'
        })()
        const senderName = (event.perspective_name ||
          s.perspectives.find(p => p.id === senderId)?.name ||
          'Agent') as string
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
            s.setTypingNames(s.typingNames.filter(n => n !== senderName))
            s.setAgentStatus(senderName, 'done')
          } else {
            s.setAgentStatus(senderName, 'composing')
            // 追加而非覆盖，保留并行场景下其他 agent 的状态
            s.setTypingNames(
              [...new Set([...s.typingNames.filter(n => n !== senderName), senderName])]
            )
          }
        }
        break
      }

      case 'speech_end': {
        const senderId = (event.perspective_id as string) || (() => {
          const sName = (event.perspective_name || 'Agent') as string
          const p = s.perspectives.find(pp => pp.name === sName)
          return p?.id || 'unknown'
        })()
        const senderName = (event.perspective_name ||
          s.perspectives.find(p => p.id === senderId)?.name ||
          'Agent') as string

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

        s.setAgentStatus(senderName, 'done')
        s.setTypingNames(s.typingNames.filter(n => n !== senderName))
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
        s.setAgentStatus(challenger, 'debating')
        s.setAgentStatus(defender, 'debating')
        s.setTypingNames([challenger])
        addMsg(mkSys(`⚔️ 第${event.round || '?'}轮 · ${challenger} 质疑 ${defender}`))
        break
      }

      case 'debate_chunk': {
        const senderName = (event.perspective_name || '') as string
        const perspective = s.perspectives.find(p => p.name === senderName)
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
        s.setAgentStatus(challenger, 'done')
        s.setAgentStatus(defender, 'done')
        s.setTypingNames([])
        if (event.judge_note) {
          s.setJudgeState('composing')
          addMsg({
            id: nextMsgId(), senderId: 'judge', senderName: '裁判',
            avatar: AVATAR_MAP['judge'],
            content: `📝 本轮小结：${event.judge_note}`,
            timestamp: now, type: 'judge',
          })
          s.setJudgeState('done')
        }
        break
      }

      case 'synthesis_start':
        s.setJudgeState('thinking')
        addMsg(mkSys('🧠 裁判开始综合分析大家的观点...'))
        break

      case 'self_reflection':
        s.setJudgeState('composing')
        {
          const iter = (event.iteration || 1) as number
          addMsg(mkSys(`🪞 裁判正在自我审查第 ${iter} 轮，检查偏见、遗漏和假共识...`))
        }
        break

      case 'decision_map_chunk':
        s.setDecisionMap((s.decisionMap || '') + (event.text || ''))
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
        s.setStatus('completed')
        s.setJudgeState('done')
        if (event.total_time_ms) s.setStats(s.totalTokens, event.total_time_ms as number)
        s.perspectives.forEach(p => s.setAgentStatus(p.name, 'done'))
        s.setTypingNames([])
        if (s.decisionMap) {
          addMsg({
            id: nextMsgId(), senderId: 'judge', senderName: '裁判',
            avatar: AVATAR_MAP['judge'],
            content: `📊 决策地图\n\n${s.decisionMap}`,
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
        s.setError((event.message || event.data?.message || '未知错误') as string)
        addMsg(mkSys(`❌ 出错了：${event.message || '未知错误'}`))
        break
    }
  }, [store, addMsg, openRightPanel])

  // 跟踪当前 sessionId，防止旧连接的 SSE 错误加载到新会话
  const currentSessionRef = useRef(sessionId)
  useEffect(() => { currentSessionRef.current = sessionId }, [sessionId])

  // SSE 连接
  const { abort } = useSSE(
    sessionId ? `/api/debate/${sessionId}/stream` : null,
    handleSSEEvent,
    () => {},
    (err) => {
      // 如果连接的 sessionId 已经不是当前页面，忽略（旧的 abort 触发的）
      if (currentSessionRef.current !== sessionId && err.includes('abort')) return
      // 404 → 可能是历史会话，尝试从 REST API 加载
      if (err.includes('404') && sessionId) {
        loadHistoryResult(sessionId)
        return
      }
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
          generating={isGenerating}
          onSelect={(id) => {
            if (isGenerating && id !== sessionId) {
              setBlockedReminder(true)
              setTimeout(() => setBlockedReminder(false), 3000)
              return
            }
            navigate(`/debate/${id}`)
          }}
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

        {/* 切换被拦截的 Toast 提示 */}
        {blockedReminder && (
          <div className="absolute top-0 left-1/2 -translate-x-1/2 z-50 mt-2 px-4 py-2 bg-marker-red/90 text-white text-sm rounded-full shadow-lg transition-all duration-300">
            ⚠️ 正在生成决策，生成完成后才能查看其他历史记录
          </div>
        )}

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
              {!sessionId && store.messages.length === 0 && store.status === 'idle' && (
                <div className="flex flex-col items-center justify-center mt-20 gap-4">
                  <span className="text-5xl">💬</span>
                  <p className="text-ink-50 text-sm">选择一个历史讨论，或发起新的决策分析</p>
                  <HandDrawnButton
                    variant="primary"
                    size="md"
                    tilt="right"
                    onClick={() => navigate('/')}
                  >
                    ✏️ 新建讨论
                  </HandDrawnButton>
                </div>
              )}

              {/* 正在加载历史消息 */}
              {loadingHistory && (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <span className="text-3xl animate-bounce">📡</span>
                  <p className="text-ink-100 text-sm font-medium">正在加载讨论记录…</p>
                  <p className="text-ink-50 text-xs">内容马上就好</p>
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
          disabled={!sessionId || store.status === 'completed' || store.status === 'error'}
          placeholder={
            !sessionId ? '请选择或新建一个讨论'
            : store.status === 'completed' ? '讨论已结束'
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
