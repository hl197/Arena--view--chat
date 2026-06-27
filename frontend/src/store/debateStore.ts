/** 辩论状态管理 */

import { create } from 'zustand'
import type { Perspective, DebateTurn, ChatMessage } from '../api/types'

/** Agent 详细状态 */
export interface AgentStateItem {
  id: string
  name: string
  avatar: string
  status: 'idle' | 'thinking' | 'searching' | 'composing' | 'debating' | 'done' | 'error'
}

const AVATAR_MAP: Record<string, string> = {
  p_01: '/avatars/cautious.png',
  p_02: '/avatars/seeker.png',
  p_03: '/avatars/analyst.png',
  p_04: '/avatars/humanist.png',
  p_05: '/avatars/thinker.png',
  p_06: '/avatars/pragmatist.png',
  judge: '/avatars/thinker.png',
}

interface DebateState {
  // 会话
  sessionId: string | null
  status: 'idle' | 'generating' | 'researching' | 'debating' | 'synthesizing' | 'completed' | 'error'
  phase: string

  // 问题
  question: string

  // 视角
  perspectives: Perspective[]

  // 群聊消息
  messages: ChatMessage[]
  typingNames: string[]

  // Agent 详细状态
  agentStatuses: Record<string, string>
  agentStates: AgentStateItem[]
  judgeState: AgentStateItem | null

  // 实时流内容
  debateTurns: DebateTurn[]

  // 结果
  decisionMap: string
  totalTokens: number
  totalTimeMs: number

  // 错误
  error: string | null

  // 操作
  setSessionId: (id: string) => void
  setQuestion: (q: string) => void
  setPhase: (phase: string) => void
  setStatus: (status: DebateState['status']) => void
  addPerspective: (p: Perspective) => void
  addMessage: (m: ChatMessage) => void
  appendToLastMessage: (text: string) => void
  setTypingNames: (names: string[]) => void
  setAgentStatus: (name: string, status: string) => void
  setJudgeState: (status: AgentStateItem['status']) => void
  addDebateTurn: (turn: DebateTurn) => void
  setDecisionMap: (text: string) => void
  setError: (err: string) => void
  setStats: (tokens: number, time: number) => void
  reset: () => void
}

let msgCounter = 0
const nextMsgId = () => `msg_${++msgCounter}_${Date.now()}`

/** 从 SSE status 映射到 AgentStateItem status */
function mapStatus(s: string): AgentStateItem['status'] {
  switch (s) {
    case 'thinking': return 'thinking'
    case 'searching': return 'searching'
    case 'researching': case 'composing': return 'composing'
    case 'debating': return 'debating'
    case 'done': case 'finishing': return 'done'
    default: return 'idle'
  }
}

export const useDebateStore = create<DebateState>((set, get) => ({
  sessionId: null,
  status: 'idle',
  phase: '',
  question: '',
  perspectives: [],
  messages: [],
  typingNames: [],
  agentStatuses: {},
  agentStates: [],
  judgeState: null,
  debateTurns: [],
  decisionMap: '',
  totalTokens: 0,
  totalTimeMs: 0,
  error: null,

  setSessionId: (id) => set({ sessionId: id }),
  setQuestion: (q) => set({ question: q }),
  setPhase: (phase) => set({ phase }),
  setStatus: (status) => set({ status }),
  addPerspective: (p) =>
    set((s) => {
      const newPerspectives = [...s.perspectives, p]
      // 同步更新 agentStates
      const agentStates: AgentStateItem[] = newPerspectives.map((persp) => {
        const existing = s.agentStates.find((a) => a.id === persp.id)
        return existing || {
          id: persp.id,
          name: persp.name,
          avatar: AVATAR_MAP[persp.id] || '/avatars/analyst.png',
          status: 'idle' as const,
        }
      })
      return { perspectives: newPerspectives, agentStates }
    }),
  addMessage: (m) =>
    set((s) => ({ messages: [...s.messages, { ...m, id: m.id || nextMsgId() }] })),
  appendToLastMessage: (text: string) => {
    set((state) => {
      const messages = [...state.messages]
      if (messages.length > 0) {
        const last = { ...messages[messages.length - 1] }
        last.content = last.content + '\n\n' + text
        messages[messages.length - 1] = last
      }
      return { messages }
    })
  },
  setTypingNames: (names) => set({ typingNames: names }),

  setAgentStatus: (name, status) =>
    set((s) => {
      const newAgentStates = s.agentStates.map((a) =>
        a.name === name ? { ...a, status: mapStatus(status) } : a
      )
      return {
        agentStatuses: { ...s.agentStatuses, [name]: status },
        agentStates: newAgentStates,
      }
    }),

  setJudgeState: (status) =>
    set((s) => ({
      judgeState: {
        id: 'judge',
        name: '裁判',
        avatar: AVATAR_MAP['judge'],
        status,
      },
    })),

  addDebateTurn: (turn) =>
    set((s) => ({ debateTurns: [...s.debateTurns, turn] })),
  setDecisionMap: (text) => set({ decisionMap: text }),
  setError: (err) => set({ error: err, status: 'error' }),
  setStats: (tokens, time) => set({ totalTokens: tokens, totalTimeMs: time }),
  reset: () =>
    set({
      sessionId: null, status: 'idle', phase: '', question: '',
      perspectives: [], messages: [], typingNames: [],
      agentStatuses: {}, agentStates: [], judgeState: null, debateTurns: [],
      decisionMap: '', totalTokens: 0, totalTimeMs: 0, error: null,
    }),
}))

export { nextMsgId, AVATAR_MAP }
