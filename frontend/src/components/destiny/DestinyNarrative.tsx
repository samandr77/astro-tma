import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { destinyApi } from "@/services/api";

const SECTION_LABELS_RU: Record<string, string> = {
  who_you_are: "Кто вы",
  karmic_tail: "Кармический хвост",
  talents: "Таланты",
  purpose: "Предназначение",
  relationships: "Отношения",
  finance: "Деньги и реализация",
  parental: "Род и семья",
  advice: "Совет",
};

// The interpreter returns this exact order in the LLM response.
const SECTION_ORDER = [
  "who_you_are", "karmic_tail", "talents", "purpose",
  "relationships", "finance", "parental", "advice",
] as const;

interface Props {
  enabled: boolean;
  /** V2: when false, free preview of 2 sections; remaining 6 render as locked. */
  hasFullAccess?: boolean;
  onUpgrade?: () => void;
}

export function DestinyNarrative({ enabled, hasFullAccess = true, onUpgrade }: Props) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["destiny-matrix", "interpretation"],
    queryFn: destinyApi.getInterpretation,
    enabled,
    staleTime: 1000 * 60 * 60 * 24 * 7, // 7 days — interpreter caches in DB anyway
  });

  if (!enabled) return null;

  if (isLoading) {
    return (
      <div className="destiny-narrative__loading">
        <p>Астролог пишет ваш разбор…</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="destiny-narrative__loading">
        <p>Не удалось загрузить разбор.</p>
        <button type="button" className="btn-ghost" onClick={() => refetch()}>
          Повторить
        </button>
      </div>
    );
  }

  if (!data) return null;

  const lockedKeys = new Set(data.locked_sections ?? []);
  const isUnlocked = data.has_full_access ?? hasFullAccess;

  return (
    <section className="destiny-narrative">
      <h3 className="destiny-narrative__title">Личный разбор</h3>
      {SECTION_ORDER.map((key, idx) => {
        const text = data.sections[key];
        if (!text) return null;
        const isLocked = lockedKeys.has(key);
        return (
          <motion.div
            key={key}
            className={`destiny-narrative__section${isLocked ? " is-locked" : ""}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * idx, duration: 0.3 }}
          >
            <h4 className="destiny-narrative__section-title">
              {SECTION_LABELS_RU[key] ?? key}
              {isLocked && <span className="destiny-narrative__lock">🔒</span>}
            </h4>
            <p className="destiny-narrative__section-text">{text}</p>
          </motion.div>
        );
      })}
      {!isUnlocked && onUpgrade && (
        <button
          type="button"
          className="btn-stars destiny-narrative__upgrade"
          onClick={onUpgrade}
        >
          Открыть полный разбор
        </button>
      )}
    </section>
  );
}
