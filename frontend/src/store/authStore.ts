/** 认证状态管理 */
import { create } from 'zustand'
import { post } from '../api/client'

interface AuthUser {
  user_id: string
  email: string
  tier: string
}

interface AuthState {
  token: string | null
  user: AuthUser | null
  isLoggedIn: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<{ user_id: string; email: string; message: string }>
  verify: (email: string, code: string) => Promise<void>
  resendCode: (email: string) => Promise<void>
  logout: () => void
  loadFromStorage: () => void
}

const AUTH_TOKEN_KEY = 'arena_auth_token'
const AUTH_USER_KEY = 'arena_auth_user'

/** API 返回的认证响应 */
interface AuthResponse {
  user_id: string
  email: string
  tier: string
  token: string
  api_key_configured?: boolean
}

/** 注册第一步响应 */
interface RegisterStep1Response {
  user_id: string
  email: string
  message: string
  requires_verification: boolean
}

/** 验证成功响应 */
interface VerifyResponse {
  user_id: string
  email: string
  tier: string
  token: string
  message: string
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  user: null,
  isLoggedIn: false,

  login: async (email: string, password: string) => {
    const res = await post<AuthResponse>('/auth/login', { email, password })
    const user: AuthUser = { user_id: res.user_id, email: res.email, tier: res.tier }
    localStorage.setItem(AUTH_TOKEN_KEY, res.token)
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
    set({ token: res.token, user, isLoggedIn: true })
  },

  register: async (email: string, password: string) => {
    const res = await post<RegisterStep1Response>('/auth/register', { email, password })
    // 不自动登录，返回信息让 UI 进入验证步骤
    return { user_id: res.user_id, email: res.email, message: res.message }
  },

  verify: async (email: string, code: string) => {
    const res = await post<VerifyResponse>('/auth/verify', { email, code })
    const user: AuthUser = { user_id: res.user_id, email: res.email, tier: res.tier }
    localStorage.setItem(AUTH_TOKEN_KEY, res.token)
    localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user))
    set({ token: res.token, user, isLoggedIn: true })
  },

  resendCode: async (email: string) => {
    await post<{ message: string }>('/auth/resend-code', { email })
  },

  logout: () => {
    localStorage.removeItem(AUTH_TOKEN_KEY)
    localStorage.removeItem(AUTH_USER_KEY)
    set({ token: null, user: null, isLoggedIn: false })
  },

  loadFromStorage: () => {
    const token = localStorage.getItem(AUTH_TOKEN_KEY)
    const userStr = localStorage.getItem(AUTH_USER_KEY)
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr) as AuthUser
        set({ token, user, isLoggedIn: true })
      } catch {
        localStorage.removeItem(AUTH_TOKEN_KEY)
        localStorage.removeItem(AUTH_USER_KEY)
      }
    }
  },
}))
