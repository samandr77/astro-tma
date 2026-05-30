import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useEntitlementStatus } from "@/hooks/useEntitlement";
import { useAppStore } from "@/stores/app";
import { useHaptic } from "@/hooks/useTelegram";

const STORAGE_KEY = "trial-soft-paywall-shown";

/**
 * Soft paywall — shows ONCE when the user's trial enters the last 24
 * hours. Decision to convert is kept frictionless: "Перейти" leads to
 * the Premium screen, "Может позже" closes and we never show again.
 */
export function TrialEndingModal() {
  const status = useEntitlementStatus();
  const { setScreen } = useAppStore();
  const { impact } = useHaptic();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!status.isTrial) return;
    if (status.daysRemaining > 1 || status.daysRemaining <= 0) return;
    try {
      if (localStorage.getItem(STORAGE_KEY)) return;
    } catch {
      /* no localStorage available — show anyway */
    }
    setOpen(true);
  }, [status.isTrial, status.daysRemaining]);

  const close = () => {
    try {
      localStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch {
      /* ignore */
    }
    setOpen(false);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="trial-modal__backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={close}
        >
          <motion.div
            className="trial-modal"
            initial={{ opacity: 0, scale: 0.94, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="trial-modal__crown" aria-hidden="true">✦</div>
            <h3 className="trial-modal__title">Ваш Premium заканчивается</h3>
            <p className="trial-modal__lead">
              Через 24 часа доступ к расширенным интерпретациям и прогнозам
              на неделю/месяц закроется. Сохраните Premium за 199⭐ в месяц.
            </p>
            <button
              type="button"
              className="btn-primary trial-modal__cta"
              onClick={() => {
                impact("light");
                close();
                setScreen("premium");
              }}
            >
              Открыть Premium
            </button>
            <button
              type="button"
              className="trial-modal__dismiss"
              onClick={close}
            >
              Может позже
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
