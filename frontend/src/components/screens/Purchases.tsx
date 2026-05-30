import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { usersApi } from "@/services/api";
import { useAppStore } from "@/stores/app";
import { useTelegramBackButton } from "@/hooks/useTelegram";

const MONTHS_RU_GENITIVE = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];

function formatPurchaseDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getDate()} ${MONTHS_RU_GENITIVE[d.getMonth()]} ${d.getFullYear()}`;
}

function formatExpiresRu(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return `до ${d.getDate()} ${MONTHS_RU_GENITIVE[d.getMonth()]} ${d.getFullYear()}`;
}

export function Purchases() {
  const { setScreen } = useAppStore();
  const goBack = () => setScreen("profile", "back");
  useTelegramBackButton(goBack, true);

  const { data, isLoading } = useQuery({
    queryKey: ["my-purchases"],
    queryFn: usersApi.getPurchases,
    staleTime: 1000 * 60 * 5,
  });

  const purchases = data?.purchases ?? [];
  const active = data?.active_subscription ?? null;

  return (
    <div className="screen purchases-screen">
      <div className="screen-header screen-header--with-back">
        <button
          type="button"
          className="back-btn"
          onClick={goBack}
          aria-label="Назад"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M13 4l-6 6 6 6" />
          </svg>
        </button>
        <div>
          <h1 className="screen-title">Мои покупки</h1>
          <p className="screen-subtitle">История платежей звёздами</p>
        </div>
      </div>

      <div className="screen-content">
        {isLoading ? (
          <div className="purchases-empty">Загружаем…</div>
        ) : purchases.length === 0 && !active ? (
          <div className="purchases-empty">
            <div className="purchases-empty__icon" aria-hidden="true">✦</div>
            <p>У вас пока нет покупок.</p>
            <button
              type="button"
              className="btn-stars"
              onClick={() => setScreen("premium")}
            >
              Открыть Premium
            </button>
          </div>
        ) : (
          <>
            <motion.div
              className="natal-card purchases-list"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
            >
              {active && (
                <div className="purchase-row purchase-row--active">
                  <div className="purchase-row__main">
                    <div className="purchase-row__title">Премиум подписка</div>
                    <div className="purchase-row__meta">
                      {formatExpiresRu(active.expires_at) ?? "активна"}
                    </div>
                  </div>
                  <div className="purchase-row__stars">
                    {active.stars_paid} ⭐
                  </div>
                </div>
              )}
              {purchases.map((p, idx) => (
                <div key={`${p.product_id}-${idx}`} className="purchase-row">
                  <div className="purchase-row__main">
                    <div className="purchase-row__title">{p.product_name}</div>
                    <div className="purchase-row__meta">
                      {formatPurchaseDate(p.created_at)}
                    </div>
                  </div>
                  <div className="purchase-row__stars">{p.stars_amount} ⭐</div>
                </div>
              ))}
            </motion.div>
          </>
        )}
      </div>
    </div>
  );
}
