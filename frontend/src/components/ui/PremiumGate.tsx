/**
 * Wraps premium content. Renders the children if the user owns this
 * product (Premium subscription or one-time purchase), otherwise shows
 * an inviting paywall card with a single Stars CTA.
 *
 * The `locked` prop is OPTIONAL and used for cases where the parent has
 * extra "is this even premium" logic (e.g. tarot spread.premium flag).
 * When omitted, the gate locks based purely on entitlement to productId.
 */

import { motion } from "framer-motion";
import { usePayment } from "@/hooks/usePayment";
import { useEntitlement } from "@/hooks/useEntitlement";
import { useProductPrice } from "@/hooks/useProductPrice";

interface PremiumGateProps {
  productId: string;
  productName: string;
  stars: number;
  children: React.ReactNode;
  /**
   * Set to `false` to always show the content (e.g. free tarot spread).
   * Set to `true` to defer to entitlement. Omit for the default behaviour
   * (defer to entitlement).
   */
  locked?: boolean;
  /** Short pitch shown above the price — what the user gets. */
  pitch?: string;
  /** Up to 3 bullet benefits. */
  benefits?: string[];
}

const DEFAULT_BENEFITS = [
  "Полный текст без обрывов",
  "Энергии по сферам жизни",
  "Конкретный совет дня",
];

export function PremiumGate({
  productId,
  productName,
  stars,
  children,
  locked,
  pitch,
  benefits,
}: PremiumGateProps) {
  const { purchase, loading, activating } = usePayment();
  const entitled = useEntitlement(productId);
  // Live price from the backend catalogue (honours admin overrides).
  // Falls back to the prop while the catalogue fetch is in flight so
  // the gate never flashes a placeholder.
  const livePrice = useProductPrice(productId);
  const displayStars = livePrice ?? stars;

  // Caller forced free access OR user is entitled → show the real content.
  if (locked === false || entitled) {
    return <>{children}</>;
  }

  const items = benefits && benefits.length > 0 ? benefits : DEFAULT_BENEFITS;

  return (
    <motion.div
      className="premium-gate premium-gate--card"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="premium-gate__halo" aria-hidden="true" />
      <div className="premium-gate__crown" aria-hidden="true">
        ✦
      </div>
      <div className="premium-gate__badge">PREMIUM</div>
      <h3 className="premium-gate__title">{productName}</h3>
      <p className="premium-gate__desc">
        {pitch ?? "Откройте полную версию за звёзды Telegram."}
      </p>
      <ul className="premium-gate__benefits">
        {items.slice(0, 3).map((b, i) => (
          <li key={i}>
            <span className="premium-gate__tick" aria-hidden="true">✓</span>
            {b}
          </li>
        ))}
      </ul>
      <div className="premium-gate__price-row">
        <div className="premium-gate__price">
          <span className="premium-gate__price-amount">{displayStars}</span>
          <span className="premium-gate__price-unit">⭐</span>
        </div>
        <span className="premium-gate__once">единоразово</span>
      </div>
      <button
        type="button"
        className="btn-stars premium-gate__cta"
        onClick={() => purchase(productId)}
        disabled={loading}
      >
        {activating
          ? "Активируем доступ…"
          : loading
            ? "Открываем Telegram…"
            : `Открыть за ${displayStars} ⭐`}
      </button>

      {activating && (
        <motion.div
          className="premium-gate__activating"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2 }}
        >
          <div className="premium-gate__spinner" aria-hidden="true" />
          <div className="premium-gate__activating-title">
            Открываем доступ
          </div>
          <div className="premium-gate__activating-sub">
            Платёж принят. Ждём подтверждение от Telegram — обычно 2-5 секунд.
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
