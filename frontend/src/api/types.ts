/** ArenaView 共享类型 */

export interface Perspective {
  id: string
  name: string
  role_label?: string
  stance: string
  core_values?: string[]
  blind_spots?: string[]
}

export interface DebateTurn {
  round: number
  challenger_name: string
  defender_name: string
  challenge: string
  defense: string
  judge_note: string
}

export interface DebateSession {
  session_id: string
  question: string
  status: 'pending' | 'running' | 'completed' | 'error'
  perspectives: Perspective[]
  arguments: Record<string, string>
  debate_transcript: DebateTurn[]
  decision_map: string
  total_tokens: number
  total_time_ms: number
}

export interface SSEEvent {
  type: string
  timestamp: number
  session_id?: string
  phase?: string
  status?: string
  perspective_name?: string
  perspective_id?: string
  text?: string
  summary?: string
  data?: Record<string, unknown>
  [key: string]: unknown
}

/** 群聊消息 */
export interface ChatMessage {
  id: string
  senderId: string       // 'user' | 'judge' | 'p_01' ...
  senderName: string     // 显示名称
  avatar?: string        // 头像路径
  content: string        // 消息内容
  timestamp: number      // unix ms
  type: 'agent' | 'user' | 'system' | 'judge'
}
