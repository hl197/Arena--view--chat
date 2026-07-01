/** API 客户端 */

import { useAuthStore } from '../store/authStore'

const BASE_URL = '/api'

/** 构建公共 headers，自动携带 token */
function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = useAuthStore.getState().token
  const headers: Record<string, string> = { ...extra }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

/** 从 HTTP 错误响应中提取用户可读的错误信息 */
async function parseError(res: Response): Promise<string> {
  try {
    const err = await res.json()
    // FastAPI HTTPException → detail 字段
    // 自定义错误 → message 字段
    return err.detail || err.message || `请求失败 (${res.status})`
  } catch {
    return `请求失败 (${res.status})`
  }
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PUT',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
