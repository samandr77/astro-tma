import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { HeaderAvatarButton } from "@/components/ui/HeaderAvatarButton";
import { paymentsApi } from "@/services/api";
import { useAppStore } from "@/stores/app";
import { useHaptic } from "@/hooks/useTelegram";
import { usePayment } from "@/hooks/usePayment";

/**
 * Premium / Stars screen — overview of available paid products and the
 * monthly subscription. Reads the catalog from the backend and renders
 * each item with its price and description.
 */
export function Premium() {
  const { user } = useAppStore();
  const { impact } = useHaptic();
  const { purchase, loading } = usePayment();

  const { data: products = [], isLoading } = useQuery({
    queryKey: ["payments-products"],
    queryFn: paymentsApi.getProducts,
    staleTime: 1000 * 60 * 5,
  });

  const monthly = products.find((p) => p.id === "subscription_month");
  const yearly = products.find((p) => p.id === "subscription_year");
  const subscriptionIds = new Set(
    [monthly?.id, yearly?.id].filter(Boolean) as string[],
  );
  const oneOffs = products.filter((p) => !subscriptionIds.has(p.id));
  const yearlySavingsPct =
    monthly && yearly
      ? Math.max(0, Math.round((1 - yearly.stars / (monthly.stars * 12)) * 100))
      : 0;

  const handleBuy = async (productId: string) => {
    impact("medium");
    await purchase(productId);
  };

  return (
    <div className="screen premium-screen">
      <div className="screen-header">
        <div>
          <h1 className="screen-title">Звёзды</h1>
          <p className="screen-subtitle">Премиум-функции и подписка</p>
        </div>
        <HeaderAvatarButton />
      </div>

      <div className="screen-content">
        {/* Premium status / hero */}
        <motion.div
          className="premium-hero glass-gold"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="premium-hero__icon" aria-hidden="true">
            ✦
          </div>
          <div className="premium-hero__title">
            {user?.is_premium ? "Премиум активен" : "ASTRO Premium"}
          </div>
          <p className="premium-hero__desc">
            {user?.is_premium
              ? "Все разделы и подробные прогнозы открыты для вас."
              : "Доступ ко всем гороскопам, полной натальной карте, раскладам Таро и синастрии."}
          </p>

          {!user?.is_premium && (monthly || yearly) && (
            <div className="premium-plans">
              {monthly && (
                <button
                  className="premium-plan"
                  onClick={() => handleBuy(monthly.id)}
                  disabled={loading}
                >
                  <span className="premium-plan__label">Месяц</span>
                  <span className="premium-plan__price">⭐ {monthly.stars}</span>
                  <span className="premium-plan__period">30 дней</span>
                </button>
              )}
              {yearly && (
                <button
                  className="premium-plan premium-plan--best"
                  onClick={() => handleBuy(yearly.id)}
                  disabled={loading}
                >
                  {yearlySavingsPct > 0 && (
                    <span className="premium-plan__badge">
                      −{yearlySavingsPct}%
                    </span>
                  )}
                  <span className="premium-plan__label">Год</span>
                  <span className="premium-plan__price">⭐ {yearly.stars}</span>
                  <span className="premium-plan__period">365 дней</span>
                </button>
              )}
            </div>
          )}
          {!user?.is_premium && loading && (
            <p className="premium-hero__hint">⏳ Открываем оплату…</p>
          )}
        </motion.div>

        {/* Catalogue */}
        {isLoading ? (
          <div className="premium-list-skeleton">
            <div className="skeleton-card" />
            <div className="skeleton-card" />
            <div className="skeleton-card" />
          </div>
        ) : (
          <>
            <h2 className="section-title">Открыть отдельно</h2>
            <div className="premium-list">
              {oneOffs.map((p) => (
                <motion.button
                  key={p.id}
                  type="button"
                  className="premium-list__item"
                  onClick={() => handleBuy(p.id)}
                  whileTap={{ scale: 0.98 }}
                  disabled={loading || user?.is_premium}
                >
                  <div className="premium-list__main">
                    <div className="premium-list__name">{p.name}</div>
                    <div className="premium-list__desc">{p.description}</div>
                  </div>
                  <div className="premium-list__price">⭐ {p.stars}</div>
                </motion.button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
