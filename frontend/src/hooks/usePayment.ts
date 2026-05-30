/**
 * Payment hook — wraps invoice creation + Stars payment in one call.
 *
 * After Telegram confirms `paid`, we poll our own purchases endpoint
 * until the webhook has actually written the row (Telegram fires
 * successful_payment a beat after the callback). Each tick refreshes
 * React Query so the PremiumGate auto-unlocks the moment the row lands.
 */

import { useCallback, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { paymentsApi, usersApi } from "@/services/api";
import { useStarsPayment } from "./useTelegram";

export type PaymentPhase = "idle" | "opening" | "activating" | "done";

interface UsePaymentResult {
  purchase: (productId: string) => Promise<boolean>;
  loading: boolean;
  /** True while Telegram has confirmed payment and we're waiting for the
   *  webhook to land + caches to refresh. UI should show a clear loader. */
  activating: boolean;
  phase: PaymentPhase;
  error: string | null;
}

const POLL_INTERVAL_MS = 800;
const POLL_MAX_ATTEMPTS = 14; // ~11s of polling — covers slow webhooks

async function _waitForPurchase(productId: string): Promise<boolean> {
  for (let i = 0; i < POLL_MAX_ATTEMPTS; i++) {
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    try {
      const data = await usersApi.getPurchases();
      const owned = data.purchases.some(
        (p) => p.product_id === productId && p.status === "completed",
      );
      if (owned) return true;
      const sub = data.active_subscription;
      if (sub && sub.plan === productId) return true;
    } catch {
      /* keep polling; transient errors are fine */
    }
  }
  return false;
}

export function usePayment(): UsePaymentResult {
  const { pay } = useStarsPayment();
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<PaymentPhase>("idle");
  const [error, setError] = useState<string | null>(null);

  const purchase = useCallback(
    async (productId: string): Promise<boolean> => {
      setPhase("opening");
      setError(null);
      try {
        // 1. Get invoice URL from our backend
        const { invoice_url } = await paymentsApi.createInvoice(productId);

        // 2. Open Telegram native payment sheet
        const paid = await pay(invoice_url);
        if (!paid) {
          setPhase("idle");
          return false;
        }

        // 3. Telegram says "paid". The successful_payment webhook + our DB
        // INSERT take a beat. Poll until the purchase row lands so the
        // PremiumGate auto-unlocks without a manual reload.
        setPhase("activating");
        const landed = await _waitForPurchase(productId);

        // Force everything to refetch — entitlement first so gates open
        // immediately, then the rest so any 402'd content retries.
        await queryClient.invalidateQueries({ queryKey: ["my-purchases"] });
        await queryClient.refetchQueries({ queryKey: ["my-purchases"] });
        await queryClient.invalidateQueries();

        setPhase("done");
        // Reset to idle after a short tick so consumers see the final
        // "done" state if they care, then we're ready for the next click.
        setTimeout(() => setPhase("idle"), 400);

        if (!landed) {
          setError(
            "Платёж прошёл, но активация задерживается. Откройте экран снова через минуту.",
          );
        }
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Payment failed");
        setPhase("idle");
        return false;
      }
    },
    [pay, queryClient],
  );

  return {
    purchase,
    loading: phase === "opening" || phase === "activating",
    activating: phase === "activating",
    phase,
    error,
  };
}
