import type { DestinyVarna as DestinyVarnaType } from "@/services/api";

interface Props {
  varna: DestinyVarnaType;
}

interface VarnaInfo {
  label: string;
  motto: string;
  professions: string;
}

const VARNA_INFO: Record<string, VarnaInfo> = {
  "Брахман": {
    label: "Брахман",
    motto: "знаю",
    professions: "Учитель, наставник, врач, учёный, философ",
  },
  "Кшатрий": {
    label: "Кшатрий",
    motto: "могу",
    professions: "Руководитель, военный, спортсмен, силовик",
  },
  "Вайшью": {
    label: "Вайшью",
    motto: "хочу",
    professions: "Бизнесмен, продавец, банкир, брокер",
  },
  "Шудра": {
    label: "Шудра",
    motto: "надо",
    professions: "Ремесленник, художник, музыкант, трендмейкер",
  },
};

// Sort entries by descending percentage so the dominant varna comes first.
function sortedVarnas(varnas: Record<string, number>): Array<[string, number]> {
  return Object.entries(varnas).sort((a, b) => b[1] - a[1]);
}

export function DestinyVarna({ varna }: Props) {
  const entries = sortedVarnas(varna.varnas);

  return (
    <section className="destiny-varna">
      <h3 className="destiny-varna__title">Варна</h3>
      <p className="destiny-varna__hint">
        Кастовое сознание по ведической системе. Числа кармы 1-9 → 4 варны.
        Доминирующая определяет тип мышления и подходящие профессии.
      </p>

      <div className="destiny-varna__bar">
        {entries.map(([name, pct]) => (
          <div
            key={name}
            className={`destiny-varna__bar-seg destiny-varna__bar-seg--${name}`}
            style={{ width: `${pct}%` }}
            title={`${name}: ${pct}%`}
          />
        ))}
      </div>

      <div className="destiny-varna__list">
        {entries.map(([name, pct]) => {
          const info = VARNA_INFO[name];
          if (!info) return null;
          return (
            <div key={name} className="destiny-varna__row">
              <div className="destiny-varna__row-head">
                <span className="destiny-varna__row-label">{info.label}</span>
                <span className="destiny-varna__row-pct">{pct}%</span>
              </div>
              <div className="destiny-varna__row-motto">«{info.motto}»</div>
              <div className="destiny-varna__row-prof">{info.professions}</div>
            </div>
          );
        })}
      </div>

      <div className="destiny-varna__expr">
        Число экспрессии: <span>{varna.expression}</span>
      </div>
    </section>
  );
}
