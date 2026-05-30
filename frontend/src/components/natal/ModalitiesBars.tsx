import type { NatalModalitiesDistribution, NatalModalityKey } from "@/types";

const COLORS: Record<NatalModalityKey, string> = {
  cardinal: "#e8b4a8",
  fixed: "#8bc89b",
  mutable: "#c5b4e8",
};

const LABELS: Record<NatalModalityKey, string> = {
  cardinal: "Кардинальная",
  fixed: "Фиксированная",
  mutable: "Мутабельная",
};

const ORDER: NatalModalityKey[] = ["cardinal", "fixed", "mutable"];

export function ModalitiesBars({
  modalities,
  onSelect,
}: {
  modalities: NatalModalitiesDistribution;
  onSelect?: () => void;
}) {
  const total =
    modalities.cardinal + modalities.fixed + modalities.mutable || 1;
  return (
    <button
      type="button"
      className="natal-modalities"
      onClick={onSelect}
      disabled={!onSelect}
    >
      <div className="natal-modalities__title">Модальности</div>
      <div className="natal-modalities__list">
        {ORDER.map((k) => {
          const value = modalities[k];
          const pct = Math.round((value / total) * 100);
          return (
            <div key={k} className="natal-modalities__row">
              <span className="natal-modalities__label">{LABELS[k]}</span>
              <span className="natal-modalities__bar">
                <span
                  className="natal-modalities__bar-fill"
                  style={{
                    width: `${pct}%`,
                    background: COLORS[k],
                  }}
                />
              </span>
              <span className="natal-modalities__value">{pct}%</span>
            </div>
          );
        })}
      </div>
    </button>
  );
}
