import { create } from 'zustand'

interface UIState {
  // 侧边栏
  sidebarWidth: number
  sidebarCollapsed: boolean
  isDragging: boolean

  // 右侧面板
  rightPanelOpen: boolean
  rightPanelTab: 'members' | 'decision-map'

  // Actions
  setSidebarWidth: (w: number) => void
  toggleSidebar: () => void
  setSidebarCollapsed: (v: boolean) => void
  setIsDragging: (v: boolean) => void

  toggleRightPanel: () => void
  setRightPanelTab: (tab: 'members' | 'decision-map') => void
  openRightPanel: (tab?: 'members' | 'decision-map') => void
  closeRightPanel: () => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarWidth: 300,
  sidebarCollapsed: false,
  isDragging: false,

  rightPanelOpen: false,
  rightPanelTab: 'members',

  setSidebarWidth: (w) => set({ sidebarWidth: Math.max(240, Math.min(480, w)) }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
  setIsDragging: (v) => set({ isDragging: v }),

  toggleRightPanel: () => set((s) => ({ rightPanelOpen: !s.rightPanelOpen })),
  setRightPanelTab: (tab) => set({ rightPanelTab: tab }),
  openRightPanel: (tab) => set({ rightPanelOpen: true, ...(tab ? { rightPanelTab: tab } : {}) }),
  closeRightPanel: () => set({ rightPanelOpen: false }),
}))
