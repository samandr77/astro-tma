import type { DestinyChannels as DestinyChannelsType } from "@/services/api";

interface TapInfo {
  num: number;
  title: string;
  context: string;
  tier: "free" | "premium";
  octagramNodeId: null;
}

interface Props {
  channels: DestinyChannelsType;
  onTap?: (info: TapInfo) => void;
}

interface ChannelDef {
  key: keyof DestinyChannelsType;
  label: string;
  caption: string;
  /** arcana_meanings.context key for arcana lookups on this row */
  context: string;
}

const STAGES = ["вход", "работа", "итог"];

const CHANNELS: ChannelDef[] = [
  { key: "karmic_tail",  label: "Кармический хвост", caption: "Главный кармический урок", context: "karmic_tail" },
  { key: "talents",      label: "Зона талантов",     caption: "Что вдохновляет, где рост", context: "talents" },
  { key: "relationships", label: "Отношения",        caption: "Какого партнёра притягиваешь", context: "relationships" },
  { key: "finance",      label: "Финансы",           caption: "Откуда деньги, профессии",     context: "finance" },
  { key: "material_karma", label: "Материальная карма", caption: "Прошлый опыт как ресурс",   context: "material_karma" },
  { key: "parental",     label: "Детско-родительский", caption: "Что пришёл от родителей",     context: "parental" },
  { key: "ancestral_father_talents", label: "Род отца · таланты", caption: "Сильные стороны линии отца", context: "ancestral" },
  { key: "ancestral_father_karma",   label: "Род отца · карма",   caption: "Что прорабатывает линия отца", context: "ancestral" },
  { key: "ancestral_mother_talents", label: "Род матери · таланты", caption: "Сильные стороны линии матери", context: "ancestral" },
  { key: "ancestral_mother_karma",   label: "Род матери · карма",   caption: "Что прорабатывает линия матери", context: "ancestral" },
];

export function DestinyChannels({ channels, onTap }: Props) {
  return (
    <section className="destiny-channels">
      <h3 className="destiny-channels__title">10 каналов</h3>
      <p className="destiny-channels__hint">
        Каждый канал — три точки: вход в энергию, работа с ней и итог.
        Нажмите на любой кружок, чтобы открыть трактовку аркана.
      </p>
      <div className="destiny-channels__list">
        {CHANNELS.map((ch) => {
          const arr = channels[ch.key];
          if (!Array.isArray(arr) || arr.length < 3) return null;
          return (
            <div key={ch.key} className="destiny-channels__row">
              <div className="destiny-channels__row-head">
                <div className="destiny-channels__row-label">{ch.label}</div>
                <div className="destiny-channels__row-caption">{ch.caption}</div>
              </div>
              <div className="destiny-channels__nodes">
                {arr.slice(0, 3).map((num, i) => (
                  <button
                    key={i}
                    type="button"
                    className="destiny-channels__node"
                    onClick={() =>
                      onTap?.({
                        num,
                        title: `${ch.label} — ${STAGES[i] ?? ""}`,
                        context: ch.context,
                        tier: "premium",
                        octagramNodeId: null,
                      })
                    }
                  >
                    <span className="destiny-channels__node-num">{num}</span>
                    <span className="destiny-channels__node-stage">
                      {STAGES[i] ?? ""}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
