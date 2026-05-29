import { create } from 'zustand'

type UiState = {
  sidebarCollapsed: boolean
  commandOpen: boolean
  activeTab: 'overview' | 'compiler' | 'runtime' | 'logs' | 'agents'
  toggleSidebar: () => void
  setCommandOpen: (open: boolean) => void
  setActiveTab: (tab: UiState['activeTab']) => void
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  commandOpen: false,
  activeTab: 'compiler',
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setCommandOpen: (open) => set({ commandOpen: open }),
  setActiveTab: (tab) => set({ activeTab: tab }),
}))
