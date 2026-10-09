"use client";

import { create } from "zustand";

import type { KnowledgeBase, User } from "@/types";

type AppState = {
  hydrated: boolean;
  token: string | null;
  user: User | null;
  knowledgeBases: KnowledgeBase[];
  activeKnowledgeBaseId: string | null;
  sidebarCollapsed: boolean;
  setHydrated: (hydrated: boolean) => void;
  signIn: (token: string, user?: User | null) => void;
  signOut: () => void;
  setKnowledgeBases: (items: KnowledgeBase[]) => void;
  setActiveKnowledgeBaseId: (id: string | null) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
};

const ACTIVE_KB_KEY = "knowflow-active-kb";

export const useAppStore = create<AppState>((set, get) => ({
  hydrated: false,
  token: null,
  user: null,
  knowledgeBases: [],
  activeKnowledgeBaseId: null,
  sidebarCollapsed: false,

  setHydrated: (hydrated) => set({ hydrated }),

  signIn: (token, user = null) => {
    window.localStorage.setItem("knowflow-token", token);
    set({ token, user });
  },

  signOut: () => {
    window.localStorage.removeItem("knowflow-token");
    window.localStorage.removeItem(ACTIVE_KB_KEY);
    set({
      token: null,
      user: null,
      knowledgeBases: [],
      activeKnowledgeBaseId: null,
    });
  },

  setKnowledgeBases: (items) => {
    const current = get().activeKnowledgeBaseId;
    const stored =
      typeof window !== "undefined"
        ? window.localStorage.getItem(ACTIVE_KB_KEY)
        : null;
    const nextId =
      (current && items.some((item) => item.id === current) && current) ||
      (stored && items.some((item) => item.id === stored) && stored) ||
      items[0]?.id ||
      null;
    if (nextId) window.localStorage.setItem(ACTIVE_KB_KEY, nextId);
    set({ knowledgeBases: items, activeKnowledgeBaseId: nextId });
  },

  setActiveKnowledgeBaseId: (id) => {
    if (id) window.localStorage.setItem(ACTIVE_KB_KEY, id);
    else window.localStorage.removeItem(ACTIVE_KB_KEY);
    set({ activeKnowledgeBaseId: id });
  },

  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
}));

export function hydrateAppStore() {
  const token = window.localStorage.getItem("knowflow-token");
  const activeKnowledgeBaseId = window.localStorage.getItem(ACTIVE_KB_KEY);
  useAppStore.setState({
    token,
    activeKnowledgeBaseId,
    hydrated: true,
  });
}
