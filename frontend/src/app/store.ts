import { create } from "zustand";

interface LiveSessionState {
  shopToken: string | null;
  viewerCount: number;
  orderCount: number;
  setShopToken: (t: string | null) => void;
  bumpViewer: () => void;
  bumpOrder: () => void;
}

export const useLiveStore = create<LiveSessionState>((set) => ({
  shopToken: null,
  viewerCount: 0,
  orderCount: 0,
  setShopToken: (t) => set({ shopToken: t }),
  bumpViewer: () => set((s) => ({ viewerCount: s.viewerCount + 1 })),
  bumpOrder: () => set((s) => ({ orderCount: s.orderCount + 1 }))
}));
