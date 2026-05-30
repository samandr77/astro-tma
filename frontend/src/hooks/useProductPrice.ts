import { useQuery } from "@tanstack/react-query";
import { paymentsApi } from "@/services/api";

/**
 * Single source of truth for product prices on the frontend. Fetches
 * the catalogue once (with admin overrides applied) and exposes a
 * lookup. Components stop hard-coding `stars: 25` — the price they
 * render always matches what Telegram will actually charge.
 */
export function useProductPrice(
  productId: string | undefined | null,
): number | undefined {
  // Same queryKey the Premium screen already uses — single shared cache.
  const { data } = useQuery({
    queryKey: ["payments-products"],
    queryFn: paymentsApi.getProducts,
    staleTime: 1000 * 60 * 5,
  });

  if (!productId || !data) return undefined;
  return data.find((p) => p.id === productId)?.stars;
}
