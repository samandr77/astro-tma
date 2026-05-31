/**
 * Global app state — Zustand store.
 * Only truly global, cross-screen state lives here.
 * Server state (horoscope data, tarot readings) stays in React Query.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserProfile } from "@/types";

export type Screen =
  | "onboarding"
  | "home"
  | "horoscopes"
  | "discover"
  | "premium"
  | "tarot"
  | "moon"
  | "natal"
  | "mac"
  | "profile"
  | "transits"
  | "synastry"
  | "synastry_invite"
  | "glossary"
  | "glossary_term"
  | "news"
  | "news_detail"
  | "referral"
  | "purchases"
  | "destiny_matrix_info"
  | "destiny_matrix_reading";

interface AppState {
  screen: Screen;
  navDirection: "forward" | "back";
  setScreen: (s: Screen, direction?: "forward" | "back") => void;

  user: UserProfile | null;
  setUser: (u: UserProfile) => void;
  clearUser: () => void;

  onboardingComplete: boolean;
  setOnboardingComplete: (v: boolean) => void;

  glossarySlug: string | null;
  setGlossarySlug: (slug: string | null) => void;

  newsId: number | null;
  setNewsId: (id: number | null) => void;

  pendingInviteToken: string | null;
  setPendingInviteToken: (token: string | null) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      screen: "onboarding",
      navDirection: "forward",
      setScreen: (screen, direction = "forward") =>
        set({ screen, navDirection: direction }),

      user: null,
      setUser: (user) => set({ user }),
      clearUser: () => set({ user: null }),

      onboardingComplete: false,
      setOnboardingComplete: (v) => set({ onboardingComplete: v }),

      glossarySlug: null,
      setGlossarySlug: (glossarySlug) => set({ glossarySlug }),

      newsId: null,
      setNewsId: (newsId) => set({ newsId }),

      pendingInviteToken: null,
      setPendingInviteToken: (pendingInviteToken) =>
        set({ pendingInviteToken }),
    }),
    {
      name: "astro-app-v1",
      partialize: (state) => ({
        onboardingComplete: state.onboardingComplete,
        pendingInviteToken: state.pendingInviteToken,
      }),
    },
  ),
);
