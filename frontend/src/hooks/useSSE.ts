/** SSE 流式消费 Hook — 带重试限制和熔断保护 */

import { useEffect, useRef, useCallback } from 'react'
import type { SSEEvent } from '../api/types'

const MAX_RETRIES = 3
const RETRY_DELAY_MS = 2000  // 基础重试间隔（指数退避）

export function useSSE(
  url: string | null,
  onEvent: (event: SSEEvent) => void,
  onComplete?: () => void,
  onError?: (err: string) => void
) {
  const abortRef = useRef<AbortController | null>(null)
  const retryCountRef = useRef(0)

  // 用 ref 保存回调，避免闭包变化导致无限重连
  const callbacksRef = useRef({ onEvent, onComplete, onError })
  callbacksRef.current = { onEvent, onComplete, onError }

  const connect = useCallback(() => {
    if (!url) return

    const controller = new AbortController()
    abortRef.current = controller

    fetch(url, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          // 4xx 客户端错误不重试（session 不存在/已过期）
          if (response.status >= 400 && response.status < 500) {
            callbacksRef.current.onError?.(`请求失败 (${response.status})`)
            return
          }
          // 5xx 服务端错误可重试
          throw new Error(`HTTP ${response.status}`)
        }

        // 连接成功，重置重试计数
        retryCountRef.current = 0

        const reader = response.body?.getReader()
        if (!reader) throw new Error('Stream not supported')

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          let currentEvent = ''
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim()
            } else if (line.startsWith('data: ') && currentEvent) {
              try {
                const data = JSON.parse(line.slice(6))
                callbacksRef.current.onEvent({ ...data, type: currentEvent })
              } catch {
                // 跳过无法解析的事件
              }
              currentEvent = ''
            }
          }
        }
      })
      .then(() => {
        retryCountRef.current = 0
        callbacksRef.current.onComplete?.()
      })
      .catch((err) => {
        if (err.name === 'AbortError') return

        retryCountRef.current += 1

        if (retryCountRef.current > MAX_RETRIES) {
          callbacksRef.current.onError?.(
            `连接失败，已重试 ${MAX_RETRIES} 次后放弃: ${err.message}`
          )
          return
        }

        // 指数退避重试
        const delay = RETRY_DELAY_MS * Math.pow(2, retryCountRef.current - 1)
        setTimeout(() => {
          if (!controller.signal.aborted) {
            connect()
          }
        }, delay)
      })
  }, [url])  // 只依赖 url，回调通过 ref 访问

  useEffect(() => {
    retryCountRef.current = 0
    connect()
    return () => abortRef.current?.abort()
  }, [connect])

  return { abort: () => abortRef.current?.abort() }
}
