import { useQuery } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import WebApp from "@twa-dev/sdk";
import { usersApi } from "@/services/api";
import { useAppStore } from "@/stores/app";
import type { SubscriptionItem } from "@/types";

export interface EntitlementStatus {
  /** True if user has any active subscription (trial or paid) OR has any
   *  one-time purchase. Mostly used in copy: "you are premium". */
  isPremium: boolean;
  /** Active subscription that's a granted trial (welcome / referral). */
  isTrial: boolean;
  /** ISO date when the active subscription expires, or null if none. */
  expiresAt: string | null;
  /** Days remaining on the active subscription. 0 if expired or absent. */
  daysRemaining: number;
  /** Optional reason string from the trial subscription row. */
  trialReason: string | null;
}

function _computeStatus(active: SubscriptionItem | null | undefined): EntitlementStatus {
  if (!active || !active.expires_at) {
    return {
      isPremium: false,
      isTrial: false,
      expiresAt: null,
      daysRemaining: 0,
      trialReason: null,
    };
  }
  const expires = new Date(active.expires_at).getTime();
  const now = Date.now();
  const ms = expires - now;
  if (ms <= 0) {
    return {
      isPremium: false,
      isTrial: false,
      expiresAt: active.expires_at,
      daysRemaining: 0,
      trialReason: active.trial_reason ?? null,
    };
  }
  return {
    isPremium: true,
    isTrial: !!active.is_trial,
    expiresAt: active.expires_at,
    daysRemaining: Math.ceil(ms / (1000 * 60 * 60 * 24)),
    trialReason: active.trial_reason ?? null,
  };
}

function isLocalBrowserWithoutTelegram(): boolean {
  if (WebApp.initData) return false;
  if (typeof window === "undefined") return false;
  return ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
}

/**
 * Trial / Premium status derived from /users/me/purchases. Use this when
 * you need to render badges or pop a soft paywall.
 */
export function useEntitlementStatus(): EntitlementStatus {
  const { data } = useQuery({
    queryKey: ["my-purchases"],
    queryFn: usersApi.getPurchases,
    staleTime: 1000 * 60 * 5,
  });
  return useMemo(
    () => _computeStatus(data?.active_subscription ?? null),
    [data?.active_subscription],
  );
}

/**
 * Returns true if the current user is entitled to `productId` content —
 * either they hold an active Premium subscription OR they bought this
 * specific product once. Keeps the list of completed purchases in
 * React Query cache so the rest of the UI can stay in sync after a
 * successful Stars payment.
 */
export function useEntitlement(productId: string | undefined | null): boolean {
  if (isLocalBrowserWithoutTelegram()) return true;

  const isPremium = useAppStore((s) => s.user?.is_premium ?? false);
  const { data } = useQuery({
    queryKey: ["my-purchases"],
    queryFn: usersApi.getPurchases,
    staleTime: 1000 * 60 * 5,
  });

  if (isPremium) return true;
  if (!productId || !data) return false;

  return data.purchases.some(
    (p) => p.product_id === productId && p.status === "completed",
  );
}

/**
 * Same backing data as `useEntitlement`, exposed as a callable predicate
 * so a single component can check several products in one render (e.g.
 * the period-tab lock icons on the Horoscopes / Transits screens).
 */
export function useEntitlementChecker(): (productId: string) => boolean {
  const isLocalDevUnlocked = isLocalBrowserWithoutTelegram();
  const isPremium = useAppStore((s) => s.user?.is_premium ?? false);
  const { data } = useQuery({
    queryKey: ["my-purchases"],
    queryFn: usersApi.getPurchases,
    staleTime: 1000 * 60 * 5,
  });

  return useCallback(
    (productId: string) => {
      if (isLocalDevUnlocked) return true;
      if (isPremium) return true;
      if (!data) return false;
      return data.purchases.some(
        (p) => p.product_id === productId && p.status === "completed",
      );
    },
    [isLocalDevUnlocked, isPremium, data],
  );
}
