import type { DestinyHealthMap as DestinyHealthMapType } from "@/services/api";

interface TapInfo {
  num: number;
  title: string;
  context: string;
  tier: "free" | "premium";
  octagramNodeId: null;
}

interface Props {
  healthMap: DestinyHealthMapType;
  onTap?: (info: TapInfo) => void;
}

/** Top→bottom display order for chakras (crown to root). */
const CHAKRA_ORDER = [
  "sahasrara", "adjna", "vishuddha", "anahata",
  "manipura", "svadhisthana", "muladhara",
] as const;

const CHAKRA_TITLES: Record<string, string> = {
  sahasrara: "Сахасрара",
  adjna: "Аджна",
  vishuddha: "Вишудха",
  anahata: "Анахата",
  manipura: "Манипура",
  svadhisthana: "Свадхистана",
  muladhara: "Муладхара",
};

const CHAKRA_ORGANS: Record<string, string> = {
  sahasrara: "связь с Высшим, духовный план",
  adjna: "интуиция, видение, глаза/уши",
  vishuddha: "самовыражение, голос, щитовидка",
  anahata: "сердце, любовь, дыхание",
  manipura: "воля, статус, ЖКТ",
  svadhisthana: "чувственность, удовольствия, деньги",
  muladhara: "тело, безопасность, корни",
};

export function DestinyHealthMap({ healthMap, onTap }: Props) {
  return (
    <section className="destiny-health">
      <h3 className="destiny-health__title">Карта здоровья</h3>
      <p className="destiny-health__hint">
        Каждая чакра описывается через три числа: энергетика (линия Неба),
        физика (линия Земли), и ключ здоровья как их сумма. Нажмите строку,
        чтобы открыть трактовку ключа.
      </p>
      <div className="destiny-health__table">
        <div className="destiny-health__head">
          <span>Чакра</span>
          <span>Энерг.</span>
          <span>Физика</span>
          <span>Ключ</span>
        </div>
        {CHAKRA_ORDER.map((key) => {
          const row = healthMap.rows.find((r) => r.chakra === key);
          if (!row) return null;
          return (
            <button
              key={key}
              type="button"
              className="destiny-health__row"
              onClick={() =>
                onTap?.({
                  num: row.key,
                  title: `${CHAKRA_TITLES[key]} — ключ здоровья`,
                  context: "material_karma",
                  tier: "premium",
                  octagramNodeId: null,
                })
              }
            >
              <span className="destiny-health__row-head">
                <span className="destiny-health__row-name">{CHAKRA_TITLES[key]}</span>
                <span className="destiny-health__row-organs">{CHAKRA_ORGANS[key]}</span>
              </span>
              <span className="destiny-health__cell">{row.energy}</span>
              <span className="destiny-health__cell">{row.physics}</span>
              <span className="destiny-health__cell destiny-health__cell--key">
                {row.key}
              </span>
            </button>
          );
        })}
        <div className="destiny-health__row destiny-health__row--system">
          <span className="destiny-health__row-head">
            <span className="destiny-health__row-name">Системный ключ</span>
            <span className="destiny-health__row-organs">Свод по столбцам</span>
          </span>
          <span className="destiny-health__cell">{healthMap.system.energy}</span>
          <span className="destiny-health__cell">{healthMap.system.physics}</span>
          <span className="destiny-health__cell destiny-health__cell--key">
            {healthMap.system.key}
          </span>
        </div>
      </div>
      <p className="destiny-health__disclaimer">
        Материал носит эзотерический характер. Это не медицинская консультация.
      </p>
    </section>
  );
}
