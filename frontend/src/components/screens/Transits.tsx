import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { EnergyBars } from "@/components/ui/EnergyBars";
import { PremiumGate } from "@/components/ui/PremiumGate";
import { HoroscopeSkeleton } from "@/components/ui/Skeleton";
import { useAppStore } from "@/stores/app";
import { useHaptic } from "@/hooks/useTelegram";
import { transitsApi } from "@/services/api";
import { ApiError } from "@/services/api";
import type {
  PeriodEvent,
  RetrogradeInfo,
  TransitAspect,
  TransitCategory,
  TransitDetails,
} from "@/types";

type Period = "today" | "week" | "month";

const PERIOD_LABELS: Record<Period, string> = {
  today: "Сегодня",
  week: "Неделя",
  month: "Месяц",
};

const ASPECT_SYMBOL: Record<string, string> = {
  conjunction: "☌",
  trine: "△",
  sextile: "⚹",
  square: "□",
  opposition: "☍",
};

const PLANET_GLYPH: Record<string, string> = {
  sun: "☉",
  moon: "☽",
  mercury: "☿",
  venus: "♀",
  mars: "♂",
  jupiter: "♃",
  saturn: "♄",
  uranus: "♅",
  neptune: "♆",
  pluto: "♇",
  ascendant: "Asc",
  descendant: "Dsc",
  medium_coeli: "MC",
  imum_coeli: "IC",
  mean_node: "☊",
  true_node: "☊",
  mean_lunar_node: "☊",
  true_lunar_node: "☊",
  mean_north_lunar_node: "☊",
  true_north_lunar_node: "☊",
  mean_south_node: "☋",
  true_south_node: "☋",
  mean_south_lunar_node: "☋",
  true_south_lunar_node: "☋",
  mean_lilith: "⚸",
  true_lilith: "⚸",
  black_moon_lilith: "⚸",
  chiron: "⚷",
};

const ZODIAC_SYMBOL: Record<string, string> = {
  aries: "♈",
  taurus: "♉",
  gemini: "♊",
  cancer: "♋",
  leo: "♌",
  virgo: "♍",
  libra: "♎",
  scorpio: "♏",
  sagittarius: "♐",
  capricorn: "♑",
  aquarius: "♒",
  pisces: "♓",
};

const CATEGORY_META: Record<
  TransitCategory,
  { label: string; color: string; bg: string }
> = {
  support: {
    label: "Поддержка",
    color: "#8bc89b",
    bg: "rgba(139, 200, 155, 0.12)",
  },
  tension: {
    label: "Напряжение",
    color: "#e88b8b",
    bg: "rgba(232, 139, 139, 0.12)",
  },
  transformation: {
    label: "Трансформация",
    color: "#c58be8",
    bg: "rgba(197, 139, 232, 0.12)",
  },
  neutral: {
    label: "Нейтрально",
    color: "#9e9ab5",
    bg: "rgba(158, 154, 181, 0.10)",
  },
};

// Personal planets get priority in sorting (the spec calls these "personal transits").
const PLANET_PRIORITY: Record<string, number> = {
  sun: 1,
  moon: 1,
  mercury: 1,
  venus: 1,
  mars: 1,
  jupiter: 2,
  saturn: 2,
  uranus: 3,
  neptune: 3,
  pluto: 3,
};

const ASPECT_HINT: Record<string, string> = {
  conjunction:
    "Две темы сливаются в одну сильную волну — то, что раньше казалось разным, сегодня работает вместе.",
  trine:
    "Сегодня всё складывается само — стоит сделать шаг, и поддержка найдётся.",
  sextile: "Окно возможностей открыто, но само не зайдёт — нужен ваш ход.",
  square:
    "Что-то трётся и мешает. Это не катастрофа — это место, где вы реально вырастете.",
  opposition:
    "Внутри тянет в две стороны сразу. Не выбирайте крайность — попробуйте найти баланс.",
};

const FREE_LIMIT = 3;

function sortTransits(aspects: TransitAspect[]): TransitAspect[] {
  return [...aspects].sort((a, b) => {
    const pa = PLANET_PRIORITY[a.transit_planet.toLowerCase()] ?? 4;
    const pb = PLANET_PRIORITY[b.transit_planet.toLowerCase()] ?? 4;
    if (pa !== pb) return pa - pb;
    return (b.weight ?? 0) - (a.weight ?? 0);
  });
}

function pickHeadline(aspects: TransitAspect[]): TransitAspect | null {
  if (aspects.length === 0) return null;
  // Tight orb + personal planet preferred.
  const tight = aspects.filter((a) => a.orb < 3);
  const pool = tight.length > 0 ? tight : aspects;
  const personal = pool.filter(
    (a) => (PLANET_PRIORITY[a.transit_planet.toLowerCase()] ?? 4) === 1,
  );
  const candidate = (personal.length > 0 ? personal : pool)[0];
  return candidate ?? null;
}

function CategoryBadge({ category }: { category: TransitCategory }) {
  const meta = CATEGORY_META[category];
  return (
    <span
      className="transit-badge"
      style={{ color: meta.color, background: meta.bg, borderColor: meta.color }}
    >
      {meta.label}
    </span>
  );
}

function splitLines(s: string | null | undefined): string[] {
  if (!s) return [];
  return s
    .split(/\n|•|·|—\s/)
    .map((l) => l.replace(/^[\s\d.)\-•·]+/, "").trim())
    .filter(Boolean);
}

function DeepDive({
  aspect,
  details,
  loading,
}: {
  aspect: TransitAspect;
  details: TransitDetails | undefined;
  loading: boolean;
}) {
  const doItems = splitLines(details?.advice_do);
  const avoidItems = splitLines(details?.advice_avoid);
  const tone =
    aspect.applying === true
      ? "Тема сейчас набирает силу — в ближайшие дни она будет ощущаться сильнее."
      : aspect.applying === false
        ? "Пик уже позади — тема постепенно отходит на второй план."
        : "Тема активна прямо сейчас.";
  return (
    <div className="deep-dive">
      <p className="deep-dive__tone">
        {tone}
        {aspect.transit_retrograde
          ? " Планета идёт в обратную сторону — эффект скорее внутрь: больше размышлений, чем внешних действий."
          : ""}
      </p>

      {details?.affected_house_topic && (
        <div className="deep-dive__block">
          <div className="deep-dive__title">Сфера, которую задевает</div>
          <p className="deep-dive__body">
            {details.affected_house_topic}
            {details.affected_house ? ` · ${details.affected_house}-й дом` : ""}
          </p>
        </div>
      )}

      {loading && !details && (
        <p className="deep-dive__loading">Подбираем советы для вас…</p>
      )}

      {doItems.length > 0 && (
        <div className="deep-dive__block">
          <div className="deep-dive__title deep-dive__title--do">
            Что сделать сегодня
          </div>
          <ul className="deep-dive__list">
            {doItems.map((line, i) => (
              <li key={`do-${i}`}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      {avoidItems.length > 0 && (
        <div className="deep-dive__block">
          <div className="deep-dive__title deep-dive__title--avoid">
            Чего лучше избежать
          </div>
          <ul className="deep-dive__list">
            {avoidItems.map((line, i) => (
              <li key={`avoid-${i}`}>{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function HeroCard({ aspect }: { aspect: TransitAspect | null }) {
  const [expanded, setExpanded] = useState(false);
  const { data: details, isLoading: detailsLoading } = useQuery({
    queryKey: [
      "transit-details",
      aspect?.transit_planet,
      aspect?.natal_planet,
      aspect?.aspect,
    ],
    queryFn: () =>
      transitsApi.getDetails({
        transit_planet: aspect!.transit_planet,
        natal_planet: aspect!.natal_planet,
        aspect: aspect!.aspect,
      }),
    enabled: !!aspect && expanded,
    staleTime: 1000 * 60 * 60 * 24,
  });
  if (!aspect) {
    return (
      <motion.div
        className="transit-hero transit-hero--calm"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="transit-hero__eyebrow">Что важно сегодня</div>
        <h3 className="transit-hero__title">Тихий день</h3>
        <p className="transit-hero__text">
          Звёзды никуда не торопят. Хороший момент, чтобы спокойно заняться
          рутиной и довести до конца то, что давно ждёт.
        </p>
      </motion.div>
    );
  }

  const meta = CATEGORY_META[aspect.category];
  const glyph =
    PLANET_GLYPH[aspect.transit_planet.toLowerCase()] ??
    PLANET_GLYPH[aspect.natal_planet.toLowerCase()] ??
    "✦";

  return (
    <motion.div
      className="transit-hero"
      style={{ borderColor: meta.color }}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="transit-hero__row">
        <div className="transit-hero__col">
          <div className="transit-hero__eyebrow">Что важно сегодня</div>
          <CategoryBadge category={aspect.category} />
        </div>
        <span className="transit-hero__glyph" style={{ color: meta.color }}>
          {glyph}
        </span>
      </div>
      <h3 className="transit-hero__title">
        {aspect.transit_planet_ru} {aspect.aspect_ru.toLowerCase()}{" "}
        {aspect.natal_planet_ru}
      </h3>
      <p className="transit-hero__text">
        {aspect.text_ru || ASPECT_HINT[aspect.aspect] || "Значимая конфигурация."}
      </p>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            className="transit-hero__extra"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
          >
            <DeepDive
              aspect={aspect}
              details={details}
              loading={detailsLoading}
            />
          </motion.div>
        )}
      </AnimatePresence>
      <button
        type="button"
        className="transit-hero__cta"
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? "Свернуть" : "Что это значит для меня →"}
      </button>
    </motion.div>
  );
}

function TransitCardV2({
  aspect,
  idx,
}: {
  aspect: TransitAspect;
  idx: number;
}) {
  const [open, setOpen] = useState(false);
  const meta = CATEGORY_META[aspect.category];
  const glyph =
    PLANET_GLYPH[aspect.transit_planet.toLowerCase()] ?? "●";
  const symbol = ASPECT_SYMBOL[aspect.aspect] ?? "·";

  return (
    <motion.button
      type="button"
      className="transit-card-v2"
      style={{ borderLeftColor: meta.color }}
      onClick={() => setOpen((v) => !v)}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: idx * 0.04, duration: 0.3 }}
      aria-expanded={open}
    >
      <div className="transit-card-v2__top">
        <CategoryBadge category={aspect.category} />
        <span className="transit-card-v2__glyph" style={{ color: meta.color }}>
          {glyph}
        </span>
      </div>
      <div className="transit-card-v2__title">
        {aspect.transit_planet_ru}
        {aspect.transit_retrograde ? " ℞" : ""}{" "}
        <span style={{ color: meta.color }}>{symbol}</span>{" "}
        {aspect.natal_planet_ru}
      </div>
      <div className="transit-card-v2__meta">
        <span>{aspect.aspect_ru}</span>
        <span>·</span>
        <span>{aspect.orb.toFixed(1)}°</span>
        {aspect.applying === true && (
          <>
            <span>·</span>
            <span style={{ color: meta.color }}>набирает силу</span>
          </>
        )}
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            className="transit-card-v2__body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
          >
            <p>
              {aspect.text_ru ||
                ASPECT_HINT[aspect.aspect] ||
                "Значимая конфигурация."}
            </p>
            {aspect.transit_retrograde && (
              <p className="transit-card-v2__sub">
                Планета идёт в обратную сторону — тема, скорее всего,
                вернётся к чему-то из прошлого: старые разговоры, давние
                решения, забытые планы.
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.button>
  );
}

const MONTHS_RU_GENITIVE = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];

const WEEKDAYS_RU = ["вс", "пн", "вт", "ср", "чт", "пт", "сб"];

function formatEventDate(iso: string): string {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return iso;
  const year = parseInt(m[1], 10);
  const month = parseInt(m[2], 10);
  const day = parseInt(m[3], 10);
  const wd = WEEKDAYS_RU[new Date(year, month - 1, day).getDay()];
  return `${wd}, ${day} ${MONTHS_RU_GENITIVE[month - 1]}`;
}

function PeriodEventCard({ event, idx }: { event: PeriodEvent; idx: number }) {
  const [open, setOpen] = useState(false);
  const meta = CATEGORY_META[event.category];
  const glyph =
    PLANET_GLYPH[(event.transit_planet ?? event.planet ?? "").toLowerCase()] ??
    "✦";

  return (
    <motion.button
      type="button"
      className="period-event-card"
      style={{ borderLeftColor: meta.color }}
      onClick={() => setOpen((v) => !v)}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(idx * 0.03, 0.4), duration: 0.25 }}
      aria-expanded={open}
    >
      <div className="period-event-card__top">
        <CategoryBadge category={event.category} />
        <span className="period-event-card__glyph" style={{ color: meta.color }}>
          {glyph}
        </span>
      </div>
      <div className="period-event-card__title">{event.title_ru}</div>
      <div className="period-event-card__meta">
        {event.kind === "aspect"
          ? `Аспект · орб ${event.orb?.toFixed(1) ?? "0.0"}°`
          : "Ингресс в новый знак"}
      </div>
      <AnimatePresence initial={false}>
        {open && event.text_ru && (
          <motion.div
            className="period-event-card__body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
          >
            <p>{event.text_ru}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.button>
  );
}

function PeriodEventsList({ events }: { events: PeriodEvent[] }) {
  // Group by date string for the day-headers.
  const groups = useMemo(() => {
    const map = new Map<string, PeriodEvent[]>();
    for (const e of events) {
      if (!map.has(e.date)) map.set(e.date, []);
      map.get(e.date)!.push(e);
    }
    return Array.from(map.entries());
  }, [events]);

  if (events.length === 0) {
    return (
      <p style={{ color: "var(--text-dim)", fontSize: 13, textAlign: "center", padding: "8px 0" }}>
        В этот период значимых событий не предвидится.
      </p>
    );
  }

  let cursor = 0;
  return (
    <div className="period-events">
      {groups.map(([dateIso, items]) => {
        const block = (
          <div key={dateIso} className="period-events__group">
            <div className="period-events__date">{formatEventDate(dateIso)}</div>
            <div className="period-events__list">
              {items.map((e) => {
                const idx = cursor++;
                return (
                  <PeriodEventCard
                    key={`${e.date}-${e.kind}-${e.transit_planet ?? e.planet}-${e.natal_planet ?? ""}-${e.aspect ?? e.to_sign}`}
                    event={e}
                    idx={idx}
                  />
                );
              })}
            </div>
          </div>
        );
        return block;
      })}
    </div>
  );
}

function RetrogradesBlock({ items }: { items: RetrogradeInfo[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="horoscope-card">
      <div className="horoscope-card__period" style={{ marginBottom: 4 }}>
        Ретрограды сейчас
      </div>
      <p
        style={{
          fontSize: 12,
          color: "var(--text-dim)",
          marginBottom: 12,
        }}
      >
        Эти планеты идут в обратную сторону — не пугайтесь, просто включите
        внимательность
      </p>
      <div className="retro-list">
        {items.map((r) => (
          <div key={r.planet} className="retro-row">
            <span className="retro-row__glyph">{r.glyph}</span>
            <div className="retro-row__col">
              <div className="retro-row__title">
                {r.planet_ru} <span className="retro-row__tag">℞ Retro</span>
              </div>
              <div className="retro-row__sub">{r.description_ru}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Transits() {
  const { setScreen } = useAppStore();
  const { user } = useAppStore();
  const { impact } = useHaptic();
  const [introOpen, setIntroOpen] = useState(false);
  const [skyOpen, setSkyOpen] = useState(false);
  const [period, setPeriod] = useState<Period>("today");
  const [showAll, setShowAll] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["transits-current"],
    queryFn: transitsApi.getCurrent,
    // 5 min in memory so revisits feel instant, but a returning user later
    // in the day still picks up the LLM-generated interpretations once the
    // backend has filled them in the background.
    staleTime: 1000 * 60 * 5,
    retry: 1,
  });

  const { data: weekData, isLoading: weekLoading } = useQuery({
    queryKey: ["transits-week"],
    queryFn: transitsApi.getWeek,
    enabled: period === "week" && !!data,
    staleTime: 1000 * 60 * 30,
    retry: 1,
  });

  const { data: monthData, isLoading: monthLoading } = useQuery({
    queryKey: ["transits-month"],
    queryFn: transitsApi.getMonth,
    enabled: period === "month" && !!data,
    staleTime: 1000 * 60 * 60,
    retry: 1,
  });

  const noBirthData = error instanceof ApiError && error.status === 422;

  const sortedAspects = useMemo(
    () => (data ? sortTransits(data.aspects) : []),
    [data],
  );
  const headline = useMemo(() => pickHeadline(sortedAspects), [sortedAspects]);
  const isPremium = user?.is_premium ?? false;
  // Week/Month transit periods now ride on Premium subscription, not on
  // standalone transit products (those were retired in launch v1.1).
  const periodProductId = "subscription_month";
  const visibleAspects =
    isPremium || showAll ? sortedAspects : sortedAspects.slice(0, FREE_LIMIT);
  const hiddenCount = Math.max(sortedAspects.length - FREE_LIMIT, 0);

  return (
    <div className="screen transits-screen">
      <div className="screen-header screen-header--with-back">
        <button
          className="back-btn"
          onClick={() => setScreen("discover", "back")}
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
        <h2 className="screen-title">Транзиты</h2>
      </div>

      <div className="screen-content">
        {isLoading && <HoroscopeSkeleton />}

        {noBirthData && (
          <div
            className="horoscope-card"
            style={{ textAlign: "center", padding: "32px 20px" }}
          >
            <p style={{ marginBottom: 16, color: "var(--text-dim)" }}>
              Заполните данные рождения, чтобы увидеть транзиты.
            </p>
            <button
              className="btn-primary"
              onClick={() => setScreen("profile")}
            >
              Перейти в профиль
            </button>
          </div>
        )}

        {error && !noBirthData && (
          <p
            style={{
              color: "var(--text-dim)",
              textAlign: "center",
              padding: "20px",
            }}
          >
            Не удалось загрузить транзиты.
          </p>
        )}

        {data && (
          <>
            <HeroCard aspect={headline} />

            <div className="horoscope-card">
              <div
                className="horoscope-card__period"
                style={{ marginBottom: 8 }}
              >
                Энергии дня
              </div>
              <EnergyBars scores={data.energy} />
            </div>

            <div className="period-tabs">
              {(["today", "week", "month"] as Period[]).map((p) => (
                <button
                  key={p}
                  className={`period-tab ${period === p ? "active" : ""}`}
                  onClick={() => {
                    impact("light");
                    setPeriod(p);
                  }}
                >
                  {PERIOD_LABELS[p]}
                  {p !== "today" && !isPremium && (
                    <svg
                      className="period-tab__lock"
                      width="10"
                      height="10"
                      viewBox="0 0 10 10"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <rect x="1.5" y="4.5" width="7" height="5" rx="1" />
                      <path d="M3 4.5V3a2 2 0 0 1 4 0v1.5" />
                    </svg>
                  )}
                </button>
              ))}
            </div>

            {period === "today" ? (
              <div className="horoscope-card">
                <div
                  className="horoscope-card__period"
                  style={{ marginBottom: 4 }}
                >
                  Что происходит сейчас
                </div>
                <p
                  style={{
                    fontSize: 12,
                    color: "var(--text-dim)",
                    marginBottom: 14,
                  }}
                >
                  Нажмите на карточку — расскажем подробнее
                </p>
                {visibleAspects.length === 0 ? (
                  <p style={{ color: "var(--text-dim)", fontSize: 13 }}>
                    Сейчас всё спокойно — больших событий по звёздам нет.
                  </p>
                ) : (
                  <div className="transits-v2-list">
                    {visibleAspects.map((a, idx) => (
                      <TransitCardV2
                        key={`${a.transit_planet}-${a.natal_planet}-${a.aspect}-${idx}`}
                        aspect={a}
                        idx={idx}
                      />
                    ))}
                  </div>
                )}
                {!isPremium && hiddenCount > 0 && (
                  <div className="transits-locked-cta">
                    <div className="transits-locked-cta__title">
                      🔒 Ещё {hiddenCount} событи
                      {hiddenCount === 1 ? "е" : "й"} в Premium
                    </div>
                    <p>
                      В Premium видна вся картина дня, разбор каждой темы и
                      что ждёт на неделю и месяц вперёд.
                    </p>
                    <button
                      className="btn-stars"
                      onClick={() => setScreen("premium")}
                    >
                      Открыть Premium
                    </button>
                  </div>
                )}
                {isPremium && sortedAspects.length > FREE_LIMIT && !showAll && (
                  <button
                    type="button"
                    className="transits-show-all"
                    onClick={() => setShowAll(true)}
                  >
                    Показать все ({sortedAspects.length})
                  </button>
                )}
              </div>
            ) : (
              <PremiumGate
                productId={periodProductId}
                productName="Premium — 30 дней"
                stars={199}
                pitch={
                  period === "week"
                    ? "Прогноз транзитов на неделю и весь Premium-доступ."
                    : "Прогноз транзитов на месяц и весь Premium-доступ."
                }
              >
                <div className="horoscope-card">
                  <div
                    className="horoscope-card__period"
                    style={{ marginBottom: 4 }}
                  >
                    {period === "week"
                      ? "Что ждёт на неделе"
                      : "Что ждёт в этом месяце"}
                  </div>
                  <p
                    style={{
                      fontSize: 12,
                      color: "var(--text-dim)",
                      marginBottom: 14,
                    }}
                  >
                    {period === "week"
                      ? "Главные аспекты и ингрессы следующих 7 дней"
                      : "Главные аспекты и ингрессы следующих 30 дней"}
                  </p>
                  {(period === "week" ? weekLoading : monthLoading) && (
                    <p style={{ color: "var(--text-dim)", fontSize: 13, textAlign: "center" }}>
                      Считаем главные события…
                    </p>
                  )}
                  {period === "week" && weekData && (
                    <PeriodEventsList events={weekData.events} />
                  )}
                  {period === "month" && monthData && (
                    <PeriodEventsList events={monthData.events} />
                  )}
                </div>
              </PremiumGate>
            )}

            <RetrogradesBlock items={data.retrogrades} />

            <button
              type="button"
              className="transit-intro"
              onClick={() => setIntroOpen((v) => !v)}
              aria-expanded={introOpen}
            >
              <span className="transit-intro__chevron">
                {introOpen ? "▾" : "▸"}
              </span>
              <span className="transit-intro__title">Что такое транзиты?</span>
            </button>
            <AnimatePresence initial={false}>
              {introOpen && (
                <motion.div
                  className="transit-intro__body"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.25 }}
                >
                  <p>
                    Простыми словами: планеты на небе двигаются, и каждый день
                    они по-разному «общаются» с тем, как сложились звёзды в
                    момент вашего рождения. Из этого складываются темы дня —
                    где-то всё идёт легко, где-то приходится напрячься.
                  </p>
                  <p>
                    <strong>Быстрые</strong> планеты (Луна, Меркурий, Венера,
                    Марс) отвечают за настроение и события дня.{" "}
                    <strong>Медленные</strong> (Юпитер, Сатурн и дальше) — за
                    большие жизненные сюжеты, которые тянутся месяцами и годами.
                  </p>
                </motion.div>
              )}
            </AnimatePresence>

            <button
              type="button"
              className="transit-intro"
              onClick={() => setSkyOpen((v) => !v)}
              aria-expanded={skyOpen}
            >
              <span className="transit-intro__chevron">
                {skyOpen ? "▾" : "▸"}
              </span>
              <span className="transit-intro__title">Карта неба сейчас</span>
            </button>
            <AnimatePresence initial={false}>
              {skyOpen && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.25 }}
                  style={{ overflow: "hidden" }}
                >
                  <div className="horoscope-card" style={{ marginTop: 8 }}>
                    <div className="sky-grid">
                      {Object.entries(data.sky).map(([planet, pos]) => (
                        <div key={planet} className="sky-cell">
                          <span className="sky-cell__glyph">
                            {PLANET_GLYPH[planet] ?? "●"}
                          </span>
                          <span className="sky-cell__sign">
                            {ZODIAC_SYMBOL[pos.sign] ?? ""} {pos.sign_ru}
                            {pos.retrograde && (
                              <span className="sky-cell__retro"> ℞</span>
                            )}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </>
        )}
      </div>
    </div>
  );
}
