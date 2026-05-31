import type {
  DestinyPurposes as DestinyPurposesType,
  DestinyPurposesFull,
} from "@/services/api";

interface TapInfo {
  num: number;
  title: string;
  context: string;
  tier: "free" | "premium";
  octagramNodeId: null;
}

interface Props {
  purposes: DestinyPurposesType;
  purposesFull?: DestinyPurposesFull;
  onTap?: (info: TapInfo) => void;
}

interface PurposeRow {
  num: number;
  label: string;
  hint: string;
  formula: string;
}

const ctx = "purpose";

// Full 8-purpose layout per spec. Falls back to 4-purpose view when the
// backend didn't return purposes_full (older readings).
function build8(p: DestinyPurposesFull): PurposeRow[] {
  return [
    { num: p.sky_personal,
      label: "Небесное личное",
      hint: "Духовная жизнь, уроки души, потенциал",
      formula: "верх + низ ромба" },
    { num: p.earth_personal,
      label: "Земное личное",
      hint: "Тело, дом, материя, поток ресурсов",
      formula: "левый + правый угол ромба" },
    { num: p.holistic_personal,
      label: "Целостное личное",
      hint: "Соединение духовного и материального",
      formula: "Небесное + Земное" },
    { num: p.father_line,
      label: "Род Отца",
      hint: "Мужская линия, отношения с мужчинами",
      formula: "верх-лево + низ-право квадрата" },
    { num: p.mother_line,
      label: "Род Матери",
      hint: "Женская линия, отношения с женщинами",
      formula: "верх-право + низ-лево квадрата" },
    { num: p.holistic_lineage,
      label: "Целостное родовое (социальное)",
      hint: "Примирение родов, проявление в социуме",
      formula: "Отец + Мать" },
    { num: p.personal_divine,
      label: "Личное Божественное",
      hint: "Путь самопознания, интуиция",
      formula: "Целостное личное + Целостное родовое" },
    { num: p.divine_mission,
      label: "Божественная миссия",
      hint: "Большой проект, влияние на мир",
      formula: "Целостное родовое + Личное Божественное" },
  ];
}

function build4(p: DestinyPurposesType): PurposeRow[] {
  return [
    { num: p.personal,  label: "Личное",     hint: "Вектор до ~40 лет",   formula: "Небо + Земля" },
    { num: p.social,    label: "Социальное", hint: "Проявление 40-60",    formula: "Отец + Мать" },
    { num: p.spiritual, label: "Духовное",   hint: "После 60, наставник", formula: "Личное + Социальное" },
    { num: p.planetary, label: "Планетарное", hint: "Высшая миссия",      formula: "Социальное + Духовное" },
  ];
}

export function DestinyPurposes({ purposes, purposesFull, onTap }: Props) {
  const rows: PurposeRow[] = purposesFull ? build8(purposesFull) : build4(purposes);
  const heading = purposesFull ? "8 предназначений" : "4 предназначения";

  return (
    <section className="destiny-purposes">
      <h3 className="destiny-purposes__title">{heading}</h3>
      <p className="destiny-purposes__hint">
        Векторы жизни по методике Ладини. Нажмите ячейку, чтобы открыть
        трактовку.
      </p>
      <div className="destiny-purposes__grid destiny-purposes__grid--8">
        {rows.map((row, i) => (
          <button
            key={i}
            type="button"
            className="destiny-purposes__cell"
            onClick={() =>
              onTap?.({
                num: row.num,
                title: row.label,
                context: ctx,
                tier: "premium",
                octagramNodeId: null,
              })
            }
          >
            <div className="destiny-purposes__num">{row.num}</div>
            <div className="destiny-purposes__label">{row.label}</div>
            <div className="destiny-purposes__cell-hint">{row.hint}</div>
            <div className="destiny-purposes__formula">{row.formula}</div>
          </button>
        ))}
      </div>
    </section>
  );
}
