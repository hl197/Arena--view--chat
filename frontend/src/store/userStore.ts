/** 用户偏好状态管理 */
import { create } from 'zustand'

export type UserGender = 'male' | 'female'

interface UserState {
  /** 用户性别（决定头像） */
  gender: UserGender
  /** 用户昵称 */
  nickname: string
  /** 设置性别 */
  setGender: (g: UserGender) => void
  /** 设置昵称 */
  setNickname: (n: string) => void
}

const AVATARS: Record<UserGender, string> = {
  male: '/avatars/user-male.svg',
  female: '/avatars/user-female.svg',
}

/** 根据性别获取头像路径 */
export function getUserAvatar(gender: UserGender): string {
  return AVATARS[gender]
}

export const useUserStore = create<UserState>((set) => ({
  gender: (localStorage.getItem('arena_user_gender') as UserGender) || 'male',
  nickname: localStorage.getItem('arena_user_nickname') || '我',
  setGender: (g) => {
    localStorage.setItem('arena_user_gender', g)
    set({ gender: g })
  },
  setNickname: (n) => {
    localStorage.setItem('arena_user_nickname', n)
    set({ nickname: n })
  },
}))
