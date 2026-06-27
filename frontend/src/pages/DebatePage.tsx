/** 群聊辩论页面 — 微信风格聊天界面 */
import { useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useDebateStore, nextMsgId, AVATAR_MAP } from '../store/debateStore'
import { useSSE } from '../hooks/useSSE'
import { post } from '../api/client'
import ChatHeader from '../components/chat/ChatHeader'
import AgentStatusBar from '../components/chat/AgentStatusBar'
import MessageBubble from '../components/chat/MessageBubble'
import ChatInput from '../components/chat/ChatInput'
import TypingIndicator from '../components/chat/TypingIndicator'
import TimeStamp from '../components/chat/TimeStamp'
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
  const scrollRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // 消息延迟队列（ref 避免闭包问题）
  const queueRef = useRef<Array<() => void>>([])
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const processingRef = useRef(false)

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
      timerRef.current = setTimeout(processNext, 4000) // 4秒间隔
    } else {
      processingRef.current = false
      timerRef.current = null
    }
  }, [])

  /** 发消息：系统/用户立即发，Agent 排队 4 秒一条 */
  const addMsg = useCallback((msg: ChatMessage) => {
    if (msg.type === 'system' || msg.type === 'user') {
      store.addMessage(msg)
      return
    }
    queueRef.current.push(() => store.addMessage(msg))
    if (!processingRef.current) {
      // 首条消息延迟 800ms（让状态栏先更新）
      timerRef.current = setTimeout(processNext, 800)
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
        if (['searching', 'researching', 'debating'].includes(rawStatus)) {
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
          // 同一人连续发片段时，合并到上一条消息
          const lastMsg = store.messages[store.messages.length - 1]
          if (isFinal === false && lastMsg && lastMsg.senderId === senderId && lastMsg.type === 'agent') {
            // 追加到上一条消息
            store.appendToLastMessage(text)
          } else {
            addMsg({
              id: nextMsgId(), senderId, senderName,
              avatar: AVATAR_MAP[senderId],
              content: text, timestamp: now, type: 'agent',
            })
          }
        }

        // 如果是最后一段，更新状态
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

      // ===== 新版群聊轮次事件 =====
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
          // 同一人连续发片段时，合并到上一条消息
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

        // 更新状态
        store.setAgentStatus(senderName, 'composing')
        store.setTypingNames([senderName])

        // 最后一段
        if (isFinal) {
          store.setTypingNames([])
          store.setAgentStatus(senderName, 'done')
        }
        break
      }

      case 'speech_end': {
        const senderName = (event.perspective_name || '') as string
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
        addMsg({
          id: nextMsgId(), senderId: 'judge', senderName: '裁判',
          avatar: AVATAR_MAP['judge'],
          content: `🔍 自我审查：${(event.text || '') as string}`,
          timestamp: now, type: 'judge',
        })
        break

      case 'decision_map_chunk':
        store.setDecisionMap((store.decisionMap || '') + (event.text || ''))
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
  }, [store, addMsg])

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

  return (
    <div className="h-screen flex flex-col bg-[#EDEDED]">
      <ChatHeader title={title} memberCount={memberCount} phase={store.phase} />

      {/* Agent 状态栏 */}
      <div className="fixed top-12 left-0 right-0 z-40 shadow-sm">
        <AgentStatusBar agents={allAgents} phase={store.phase} />
      </div>

      {/* 消息区域 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto pt-[108px] pb-20"
        style={{ scrollBehavior: 'smooth' }}>
        <div className="max-w-2xl mx-auto">
          {store.messages.length === 0 && store.status === 'idle' && (
            <div className="flex justify-center mt-8">
              <span className="text-xs text-gray-400 bg-gray-200/60 rounded px-3 py-1">
                等待辩论开始...
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
            <div className="flex justify-center gap-3 my-6">
              <button onClick={() => navigate(`/result/${sessionId}`)}
                className="bg-white border border-gray-300 text-gray-700 hover:bg-gray-50 px-5 py-2 rounded-lg text-sm">
                📊 查看决策报告
              </button>
              <button onClick={() => navigate('/')}
                className="bg-[#07C160] text-white hover:bg-[#06AD56] px-5 py-2 rounded-lg text-sm">
                发起新辩论
              </button>
            </div>
          )}

          {store.status === 'error' && (
            <div className="flex flex-col items-center gap-3 my-8">
              <span className="text-4xl">😞</span>
              <p className="text-sm text-gray-500">{store.error || '出了点问题'}</p>
              <button onClick={() => navigate('/')}
                className="bg-[#07C160] text-white px-5 py-2 rounded-lg text-sm">
                返回首页重试
              </button>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      <ChatInput
        onSend={handleUserSend}
        disabled={store.status === 'completed' || store.status === 'error'}
        placeholder={
          store.status === 'completed' ? '辩论已结束'
          : store.status === 'error' ? '辩论出错'
          : '参与讨论...'
        }
      />

      {store.status !== 'completed' && store.status !== 'error' && store.status !== 'idle' && (
        <div className="fixed bottom-24 right-4 z-50">
          <button onClick={handleCancel}
            className="bg-white/90 border border-gray-300 text-gray-500 hover:text-red-500 px-3 py-1.5 rounded-full text-xs shadow-lg">
            结束辩论
          </button>
        </div>
      )}
    </div>
  )
}
