import {
  type CSSProperties,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useQuery } from "@tanstack/react-query";
import WebApp from "@twa-dev/sdk";
import { motion, type PanInfo } from "framer-motion";
import { NatalBasicSkeleton } from "@/components/ui/Skeleton";
import { useAppStore } from "@/stores/app";
import { ApiError, natalApi } from "@/services/api";
import {
  ZODIAC_SIGNS,
  type NatalDescriptionsResponse,
  type NatalFullResponse,
  type NatalSummaryResponse,
} from "@/types";
import { NatalChart, type NatalChartData } from "@/components/NatalChart";
import { ZodiacIcon } from "@/components/ui/ZodiacIcon";
import type { ZodiacSign } from "@/components/NatalChart/types";
import { toNatalChartData } from "@/components/NatalChart/adapter";
import { PlanetOrb } from "@/components/NatalChart/PlanetOrb";
import { AspectOrb } from "@/components/NatalChart/AspectOrb";
import {
  CosmicElementOrb,
  type ElementId,
} from "@/components/NatalChart/CosmicElementOrb";
import { NatalDescriptionSheet } from "./NatalDescriptionSheet";
import { useEntitlement } from "@/hooks/useEntitlement";
import { usePayment } from "@/hooks/usePayment";
import { useProductPrice } from "@/hooks/useProductPrice";
import {
  ASPECT_FALLBACK_DESC,
  ASPECT_PAIR_FALLBACK_HINT,
  ELEMENT_FALLBACK_DESC,
  HOUSE_FALLBACK_DESC,
  PLANET_FALLBACK_DESC,
  TRAIT_FALLBACK_DESC,
} from "@/utils/natalFallbacks";
import { BigThreeBlock } from "@/components/natal/BigThreeBlock";
import { DominantsBlock } from "@/components/natal/DominantsBlock";
import { HeroInfo } from "@/components/natal/HeroInfo";
import { KeyAspectsList } from "@/components/natal/KeyAspectsList";
import type {
  NatalElementKey,
  NatalKeyAspect,
} from "@/types";
import styles from "./Natal.module.css";

type NatalDescSelection = {
  title: string;
  subtitle?: string;
  symbol?: string;
  body: string | null;
  accent?: string;
};

type NatalTab = "circle" | "elements" | "planets" | "houses" | "aspects";
type ReadingSection = { title?: string; body: string };
type NatalInterpretationSlide = {
  id: string;
  label: string;
  title: string;
  body: string;
};

const NATAL_TABS: { key: NatalTab; label: string }[] = [
  { key: "circle", label: "Карта" },
  { key: "elements", label: "Стихии" },
  { key: "planets", label: "Планеты" },
  { key: "houses", label: "Дома" },
  { key: "aspects", label: "Аспекты" },
];

const SWIPE_OFFSET_THRESHOLD = 60;
const SWIPE_VELOCITY_THRESHOLD = 500;

type HouseAxisLabel =
  | "Асцендент"
  | "Основание"
  | "Десцендент"
  | "Середина неба";

const HOUSE_AXIS_LABELS: Record<number, HouseAxisLabel> = {
  1: "Асцендент",
  4: "Основание",
  7: "Десцендент",
  10: "Середина неба",
};

const ZODIAC_KEYS = new Set<string>([
  "aries", "taurus", "gemini", "cancer", "leo", "virgo",
  "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
]);
const toZodiacSign = (key: string | null | undefined): ZodiacSign | null =>
  key && ZODIAC_KEYS.has(key) ? (key as ZodiacSign) : null;

// Legacy unicode fallback table — kept only for non-icon contexts (e.g. card
// title strings). Visual renders below should use <ZodiacIcon>.
const ZODIAC_GLYPHS: Record<string, string> = {
  aries: "♈",
  taurus: "♉",
  gemini: "♊",
  cancer: "♋",
  leo: "♌",
  virgo: "♍",
  libra: "♎",
  scorpio: "♏︎",
  sagittarius: "♐︎",
  capricorn: "♑︎",
  aquarius: "♒︎",
  pisces: "♓︎",
};

const ZODIAC_TONES: Record<string, string> = {
  aries: "coral",
  taurus: "green",
  gemini: "violet",
  cancer: "blue",
  leo: "gold",
  virgo: "gold",
  libra: "teal",
  scorpio: "rose",
  sagittarius: "gold",
  capricorn: "violet",
  aquarius: "blue",
  pisces: "aqua",
};

type ConstellationDefinition = {
  stars: [number, number, number][];
  lines: [number, number][];
};

const ZODIAC_CONSTELLATIONS: Record<string, ConstellationDefinition> = {
  aries: {
    stars: [
      [160, 40, 1.4],
      [120, 52, 1],
      [88, 66, 0.95],
      [68, 90, 0.9],
    ],
    lines: [
      [0, 1],
      [1, 2],
      [2, 3],
    ],
  },
  taurus: {
    stars: [
      [42, 30, 1],
      [78, 58, 0.95],
      [108, 78, 1.5],
      [128, 100, 0.85],
      [152, 70, 1],
      [178, 36, 1],
    ],
    lines: [
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 4],
      [4, 5],
      [2, 4],
    ],
  },
  gemini: {
    stars: [
      [55, 28, 1.4],
      [92, 38, 1.4],
      [50, 60, 0.9],
      [92, 70, 0.9],
      [38, 92, 0.85],
      [98, 100, 0.85],
      [22, 118, 0.95],
      [128, 118, 0.95],
      [148, 78, 0.85],
    ],
    lines: [
      [0, 2],
      [2, 4],
      [4, 6],
      [1, 3],
      [3, 5],
      [5, 7],
      [2, 3],
      [3, 8],
    ],
  },
  cancer: {
    stars: [
      [100, 78, 1.3],
      [98, 42, 0.95],
      [148, 70, 1],
      [105, 118, 0.9],
      [52, 80, 0.95],
    ],
    lines: [
      [0, 1],
      [0, 2],
      [0, 3],
      [0, 4],
    ],
  },
  leo: {
    stars: [
      [62, 100, 1.5],
      [62, 78, 0.85],
      [78, 56, 1.05],
      [70, 36, 0.9],
      [50, 32, 0.85],
      [38, 50, 0.9],
      [128, 64, 1],
      [122, 92, 0.95],
      [172, 76, 1],
    ],
    lines: [
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 4],
      [4, 5],
      [5, 1],
      [0, 7],
      [7, 6],
      [6, 8],
      [7, 8],
      [2, 6],
    ],
  },
  virgo: {
    stars: [
      [104, 122, 1.5],
      [82, 96, 0.9],
      [88, 72, 1],
      [114, 56, 0.9],
      [150, 40, 1],
      [42, 60, 0.9],
      [62, 86, 0.85],
      [38, 28, 0.85],
    ],
    lines: [
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 4],
      [2, 6],
      [6, 5],
      [5, 7],
    ],
  },
  libra: {
    stars: [
      [60, 100, 1.05],
      [108, 50, 1.4],
      [42, 50, 0.9],
      [148, 100, 0.95],
      [172, 78, 0.9],
    ],
    lines: [
      [2, 1],
      [1, 0],
      [0, 3],
      [3, 4],
      [1, 3],
      [1, 4],
    ],
  },
  scorpio: {
    stars: [
      [22, 50, 0.95],
      [50, 38, 0.9],
      [80, 56, 1],
      [105, 78, 1.55],
      [120, 100, 0.9],
      [134, 118, 0.9],
      [156, 124, 0.95],
      [176, 104, 0.95],
      [184, 76, 0.95],
      [168, 56, 1],
    ],
    lines: [
      [0, 2],
      [1, 2],
      [2, 3],
      [3, 4],
      [4, 5],
      [5, 6],
      [6, 7],
      [7, 8],
      [8, 9],
    ],
  },
  sagittarius: {
    stars: [
      [88, 38, 1.05],
      [56, 56, 1.05],
      [38, 76, 0.9],
      [78, 78, 0.9],
      [124, 56, 1.4],
      [156, 70, 0.95],
      [144, 96, 1.05],
      [104, 102, 0.95],
      [72, 96, 0.9],
    ],
    lines: [
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 8],
      [8, 7],
      [7, 6],
      [6, 5],
      [5, 4],
      [4, 0],
      [1, 3],
    ],
  },
  capricorn: {
    stars: [
      [44, 50, 1.4],
      [62, 44, 0.95],
      [104, 32, 0.9],
      [148, 42, 0.95],
      [172, 64, 1.05],
      [134, 100, 0.9],
      [98, 118, 0.95],
      [62, 100, 0.9],
    ],
    lines: [
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 4],
      [4, 5],
      [5, 6],
      [6, 7],
      [7, 0],
    ],
  },
  aquarius: {
    stars: [
      [44, 44, 1],
      [86, 38, 1.4],
      [124, 50, 0.95],
      [108, 70, 0.9],
      [86, 78, 0.85],
      [134, 84, 0.9],
      [122, 104, 0.85],
      [148, 116, 0.9],
      [166, 96, 0.85],
    ],
    lines: [
      [0, 1],
      [1, 2],
      [1, 3],
      [3, 4],
      [3, 5],
      [5, 6],
      [6, 7],
      [7, 8],
    ],
  },
  pisces: {
    stars: [
      [30, 38, 0.95],
      [50, 28, 1.4],
      [60, 48, 0.9],
      [42, 56, 0.85],
      [78, 64, 0.9],
      [102, 78, 1],
      [128, 88, 0.9],
      [152, 100, 1],
      [170, 86, 0.9],
      [160, 70, 1],
      [142, 80, 0.85],
    ],
    lines: [
      [0, 1],
      [1, 2],
      [2, 3],
      [3, 0],
      [2, 4],
      [4, 5],
      [5, 6],
      [6, 7],
      [7, 8],
      [8, 9],
      [9, 10],
      [10, 7],
    ],
  },
};

function cleanReadingMarkdown(text: string): string {
  return text
    .replace(/^[ \t]*#{1,6}[ \t]*/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*\n]+)\*/g, "$1")
    .replace(/^[ \t]*[-*][ \t]+/gm, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// Split LLM reading by **Section** markers into reusable slide data.
function parseReadingSections(text: string): ReadingSection[] {
  const cleaned = text.replace(/^#[^\n]*\n?/, "").trim();
  if (!cleaned) return [];

  // Split into segments: ["intro text", "SectionTitle", "body", "SectionTitle", "body", ...]
  const parts = cleaned.split(/\*\*([^*]+)\*\*/);

  const blocks: ReadingSection[] = [];
  let i = 0;

  // If text starts before first **, treat as intro
  if (parts[0].trim()) {
    blocks.push({ body: cleanReadingMarkdown(parts[0]) });
  }
  i = 1;

  while (i < parts.length) {
    const title = cleanReadingMarkdown(parts[i] ?? "");
    const body = cleanReadingMarkdown(parts[i + 1] ?? "");
    if (title) blocks.push({ title, body });
    i += 2;
  }

  return blocks.filter((block) => block.title || block.body);
}

function NatalInterpretationSlider({
  slides,
}: {
  slides: NatalInterpretationSlide[];
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const tabsRef = useRef<HTMLDivElement | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (activeIndex > slides.length - 1) {
      setActiveIndex(Math.max(slides.length - 1, 0));
    }
  }, [activeIndex, slides.length]);

  useEffect(() => {
    const tabs = tabsRef.current;
    const activeTab = tabRefs.current[activeIndex];
    if (!tabs || !activeTab) return;

    const centeredLeft =
      activeTab.offsetLeft - tabs.clientWidth / 2 + activeTab.clientWidth / 2;
    tabs.scrollTo({
      left: Math.max(0, centeredLeft),
      behavior: "smooth",
    });
  }, [activeIndex]);

  if (slides.length === 0) return null;

  const activeSlide =
    slides[Math.min(activeIndex, slides.length - 1)] ?? slides[0];
  const canGoPrevious = activeIndex > 0;
  const canGoNext = activeIndex < slides.length - 1;

  const goToSlide = (index: number) => {
    setActiveIndex(Math.max(0, Math.min(slides.length - 1, index)));
  };

  const handleDragEnd = (
    _: MouseEvent | TouchEvent | PointerEvent,
    info: PanInfo,
  ) => {
    const shouldGoNext =
      info.offset.x < -SWIPE_OFFSET_THRESHOLD ||
      info.velocity.x < -SWIPE_VELOCITY_THRESHOLD;
    const shouldGoPrevious =
      info.offset.x > SWIPE_OFFSET_THRESHOLD ||
      info.velocity.x > SWIPE_VELOCITY_THRESHOLD;

    if (shouldGoNext) {
      goToSlide(activeIndex + 1);
    } else if (shouldGoPrevious) {
      goToSlide(activeIndex - 1);
    }
  };

  return (
    <div className="natal-interpretation-slider">
      <div className="natal-interpretation-tabs" role="tablist" ref={tabsRef}>
        {slides.map((slide, index) => (
          <button
            key={slide.id}
            ref={(node) => {
              tabRefs.current[index] = node;
            }}
            type="button"
            role="tab"
            aria-selected={index === activeIndex}
            className={`natal-interpretation-tab${
              index === activeIndex ? " is-active" : ""
            }`}
            onClick={() => goToSlide(index)}
          >
            {slide.label}
          </button>
        ))}
      </div>

      <div className="natal-interpretation-progress">
        <div
          className="natal-interpretation-controls"
          aria-label="Переключение слайдов интерпретации"
        >
          <button
            type="button"
            className="natal-interpretation-nav"
            onClick={() => goToSlide(activeIndex - 1)}
            disabled={!canGoPrevious}
            aria-label="Предыдущий слайд"
          >
            <span aria-hidden="true">‹</span>
            <span>Назад</span>
          </button>
          <div className="natal-interpretation-progress__count">
            {activeIndex + 1}/{slides.length}
          </div>
          <button
            type="button"
            className="natal-interpretation-nav"
            onClick={() => goToSlide(activeIndex + 1)}
            disabled={!canGoNext}
            aria-label="Следующий слайд"
          >
            <span>Далее</span>
            <span aria-hidden="true">›</span>
          </button>
        </div>
        <div className="natal-interpretation-dots">
          {slides.map((slide, index) => {
            const distance = Math.abs(index - activeIndex);
            const sizeClass =
              distance === 0
                ? " is-active"
                : distance === 1
                  ? " is-near"
                  : distance === 2
                    ? " is-mid"
                    : "";

            return (
              <button
                key={`dot-${slide.id}`}
                type="button"
                className={`natal-interpretation-dot${sizeClass}`}
                onClick={() => goToSlide(index)}
                aria-label={`Открыть слайд ${index + 1}`}
              />
            );
          })}
        </div>
      </div>

      <div className="natal-interpretation-stage">
        <motion.div
          key={activeSlide.id}
          className="natal-interpretation-slide"
          drag={slides.length > 1 ? "x" : false}
          dragConstraints={{ left: 0, right: 0 }}
          dragElastic={0.18}
          onDragEnd={handleDragEnd}
          initial={{ opacity: 0, x: 18 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.22, ease: "easeOut" }}
        >
          <div className="natal-interpretation-slide__head">
            <h3 className="natal-interpretation-slide__title">
              {activeSlide.title}
            </h3>
          </div>
          <p className="natal-interpretation-slide__text">{activeSlide.body}</p>
        </motion.div>
      </div>
    </div>
  );
}

// Backend returns English sign names — translate to Russian
const SIGN_EN_TO_RU: Record<string, string> = {
  Aries: "Овен",
  Taurus: "Телец",
  Gemini: "Близнецы",
  Cancer: "Рак",
  Leo: "Лев",
  Virgo: "Дева",
  Libra: "Весы",
  Scorpio: "Скорпион",
  Sagittarius: "Стрелец",
  Capricorn: "Козерог",
  Aquarius: "Водолей",
  Pisces: "Рыбы",
};
const toRu = (s: string | null | undefined) =>
  s
    ? (SIGN_EN_TO_RU[s.charAt(0).toUpperCase() + s.slice(1).toLowerCase()] ??
      ZODIAC_SIGNS.find((sign) => sign.value === s.toLowerCase())?.label ??
      s)
    : "—";

function getPdfDownloadError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 402) {
      return "PDF доступен после покупки полной натальной карты.";
    }
    if (error.status === 422) {
      return "Для PDF нужны дата, время и город рождения.";
    }
    return error.message || "Не удалось подготовить PDF.";
  }

  return "Не удалось подготовить PDF. Попробуйте ещё раз.";
}

const ELEMENT_COLORS: Record<string, string> = {
  fire: "#ff6b6b",
  earth: "#3dd68c",
  air: "#b08ef0",
  water: "#8bb8f0",
};

const ELEMENTS: Record<string, { label: string; signs: string[] }> = {
  fire: { label: "Огонь", signs: ["Aries", "Leo", "Sagittarius"] },
  earth: { label: "Земля", signs: ["Taurus", "Virgo", "Capricorn"] },
  air: { label: "Воздух", signs: ["Gemini", "Libra", "Aquarius"] },
  water: { label: "Вода", signs: ["Cancer", "Scorpio", "Pisces"] },
};

const ELEMENT_ORDER = ["fire", "earth", "air", "water"];

const ELEMENT_META: Record<
  string,
  { subtitle: string; toneClass: string; accent: string }
> = {
  fire: {
    subtitle: "Энергия · Действие",
    toneClass: "fire",
    accent: "#ff8b66",
  },
  earth: {
    subtitle: "Стабильность · Тело",
    toneClass: "earth",
    accent: "#93ee82",
  },
  air: {
    subtitle: "Мысли · Общение",
    toneClass: "air",
    accent: "#bb7cff",
  },
  water: {
    subtitle: "Эмоции · Интуиция",
    toneClass: "water",
    accent: "#67c9ff",
  },
};

const SIGN_TRAITS: Record<string, string[]> = {
  Aries: [
    "Смелый",
    "Энергичный",
    "Лидер",
    "Импульсивный",
    "Прямолинейный",
    "Нетерпеливый",
  ],
  Taurus: [
    "Стабильный",
    "Чувственный",
    "Практичный",
    "Верный",
    "Упрямый",
    "Надёжный",
  ],
  Gemini: [
    "Общительный",
    "Любознательный",
    "Остроумный",
    "Переменчивый",
    "Адаптивный",
    "Двойственный",
  ],
  Cancer: [
    "Заботливый",
    "Интуитивный",
    "Эмоциональный",
    "Защитник",
    "Домашний",
    "Чувствительный",
  ],
  Leo: [
    "Харизматичный",
    "Творческий",
    "Щедрый",
    "Гордый",
    "Драматичный",
    "Вдохновляющий",
  ],
  Virgo: [
    "Аналитичный",
    "Практичный",
    "Трудолюбивый",
    "Скромный",
    "Перфекционист",
    "Внимательный",
  ],
  Libra: [
    "Гармоничный",
    "Дипломатичный",
    "Справедливый",
    "Эстетичный",
    "Нерешительный",
    "Обаятельный",
  ],
  Scorpio: [
    "Страстный",
    "Глубокий",
    "Проницательный",
    "Сильный",
    "Магнетичный",
    "Трансформатор",
  ],
  Sagittarius: [
    "Свободный",
    "Оптимист",
    "Философ",
    "Искатель",
    "Честный",
    "Авантюрный",
  ],
  Capricorn: [
    "Амбициозный",
    "Дисциплинированный",
    "Терпеливый",
    "Ответственный",
    "Стратег",
    "Серьёзный",
  ],
  Aquarius: [
    "Оригинальный",
    "Независимый",
    "Гуманист",
    "Визионер",
    "Бунтарь",
    "Прогрессивный",
  ],
  Pisces: [
    "Интуитивный",
    "Мечтательный",
    "Сострадательный",
    "Творческий",
    "Эмпатичный",
    "Мистический",
  ],
};

// ── Planet symbols ──────────────────────────────────────────────────────────
const PLANET_SYMBOLS: Record<string, string> = {
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
};

const PLANET_ROWS = [
  {
    key: "sun",
    name: "Солнце",
    symbol: "☉",
    desc: "Ядро личности, творческая сила, воля и жизненная энергия.",
    tone: "sun",
    rgb: "255, 178, 76",
    color: "#ffb24c",
  },
  {
    key: "moon",
    name: "Луна",
    symbol: "☽",
    desc: "Эмоции, интуиция, потребность в безопасности и душевный ритм.",
    tone: "moon",
    rgb: "170, 150, 240",
    color: "#aa96f0",
  },
  {
    key: "mercury",
    name: "Меркурий",
    symbol: "☿",
    desc: "Мышление, коммуникация, способность к обучению и анализу.",
    tone: "mercury",
    rgb: "124, 214, 245",
    color: "#7cd6f5",
  },
  {
    key: "venus",
    name: "Венера",
    symbol: "♀",
    desc: "Любовь, ценности, вкус, притяжение и гармония в отношениях.",
    tone: "venus",
    rgb: "236, 134, 196",
    color: "#ec86c4",
  },
  {
    key: "mars",
    name: "Марс",
    symbol: "♂",
    desc: "Энергия, действия, амбиции и стремление к достижению целей.",
    tone: "mars",
    rgb: "236, 92, 70",
    color: "#ec5c46",
  },
  {
    key: "jupiter",
    name: "Юпитер",
    symbol: "♃",
    desc: "Рост, мудрость, удача и широкий взгляд на смысл жизни.",
    tone: "jupiter",
    rgb: "230, 182, 110",
    color: "#e6b66e",
  },
  {
    key: "saturn",
    name: "Сатурн",
    symbol: "♄",
    desc: "Дисциплина, структура, уроки времени и зрелая ответственность.",
    tone: "saturn",
    rgb: "160, 134, 230",
    color: "#a086e6",
  },
];

const PLANET_RU: Record<string, string> = {
  sun: "Солнце",
  moon: "Луна",
  mercury: "Меркурий",
  venus: "Венера",
  mars: "Марс",
  jupiter: "Юпитер",
  saturn: "Сатурн",
  uranus: "Уран",
  neptune: "Нептун",
  pluto: "Плутон",
};

const PLANET_ACCENTS: Record<string, string> = {
  sun: "#ffd36e",
  moon: "#b991ff",
  mercury: "#7ec5ff",
  venus: "#f37bd9",
  mars: "#ff8467",
  jupiter: "#b77cff",
  saturn: "#c58cff",
};

const PLANET_HERO_SYMBOLS = ["♄", "♆", "♃", "♇", "♀", "☉", "☿", "☽"];

const HOUSE_HERO_SYMBOLS = [
  "♑︎",
  "♓︎",
  "♈",
  "♏︎",
  "♎",
  "♐︎",
  "♉",
  "♊",
  "♋",
  "♌",
  "♍",
  "♎",
];

const CATEGORY_RU: Record<string, string> = {
  personality: "Личность",
  emotion: "Эмоции",
  communication: "Общение",
  love: "Любовь",
  career: "Действие",
  growth: "Рост и удача",
  discipline: "Дисциплина",
  house: "Дом",
  aspect: "Аспект",
};

const ASPECT_ORDER = [
  "conjunction",
  "trine",
  "sextile",
  "square",
  "opposition",
  "quincunx",
];

const ASPECT_META: Record<
  string,
  { name: string; symbol: string; accent: string }
> = {
  conjunction: { name: "Соединение", symbol: "☌", accent: "#ff9b63" },
  trine: { name: "Трин", symbol: "△", accent: "#d47cff" },
  sextile: { name: "Секстиль", symbol: "✶", accent: "#c36cff" },
  square: { name: "Квадрат", symbol: "□", accent: "#8d96ff" },
  opposition: { name: "Оппозиция", symbol: "☍", accent: "#ff8467" },
  quincunx: { name: "Квинконс", symbol: "⚻", accent: "#8ec7ff" },
};

const POINT_SYMBOLS: Record<string, string> = {
  ascendant: "AC",
  descendant: "DC",
  medium_coeli: "MC",
  imum_coeli: "IC",
  true_north_lunar_node: "☊",
  true_south_lunar_node: "☋",
  mean_lilith: "⚸",
  chiron: "⚷",
};

const POINT_RU: Record<string, string> = {
  ascendant: "Асцендент",
  descendant: "Десцендент",
  mediumcoeli: "Середина неба",
  medium_coeli: "Середина неба",
  midheaven: "Середина неба",
  mc: "Середина неба",
  imumcoeli: "Основание неба",
  imum_coeli: "Основание неба",
  ic: "Основание неба",
  truenorthlunarnode: "Северный узел",
  true_north_lunar_node: "Северный узел",
  northnode: "Северный узел",
  north_lunar_node: "Северный узел",
  truesouthlunarnode: "Южный узел",
  true_south_lunar_node: "Южный узел",
  southnode: "Южный узел",
  south_lunar_node: "Южный узел",
  meanlilith: "Лилит",
  mean_lilith: "Лилит",
  lilith: "Лилит",
  chiron: "Хирон",
};

const DATE_FORMATTER = new Intl.DateTimeFormat("ru-RU", {
  day: "numeric",
  month: "long",
  timeZone: "UTC",
  year: "numeric",
});

const ELEMENT_TONE: Record<
  string,
  { adjective: string; description: string; color: string }
> = {
  fire: {
    adjective: "огненная",
    description: "Инициатива, импульс и смелость в действиях",
    color: "#ffb36a",
  },
  earth: {
    adjective: "земная",
    description: "Практичность, устойчивость и чувство формы",
    color: "#7de2a8",
  },
  air: {
    adjective: "воздушная",
    description: "Идеи, связи и лёгкость мышления",
    color: "#c7b2ff",
  },
  water: {
    adjective: "водная",
    description: "Интуиция, глубина и эмоциональная память",
    color: "#8ec7ff",
  },
};

const FOCUS_PHRASES: Record<string, string> = {
  Aries: "Фокус на смелом старте",
  Taurus: "Фокус на устойчивости",
  Gemini: "Фокус на ясном слове",
  Cancer: "Фокус на внутренней опоре",
  Leo: "Фокус на самовыражении",
  Virgo: "Фокус на точности",
  Libra: "Фокус на гармонии",
  Scorpio: "Фокус на трансформации",
  Sagittarius: "Фокус на расширении",
  Capricorn: "Фокус на стратегии",
  Aquarius: "Фокус на свободе мышления",
  Pisces: "Фокус на интуиции",
};

function normalizeSign(value: string | null | undefined): string {
  if (!value) return "";
  const lower = value.toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

function signKey(value: string | null | undefined): string {
  return value?.toLowerCase() ?? "";
}

function formatBirthDate(value: string | null | undefined): string {
  if (!value) return "Дата рождения не указана";

  const [datePart] = value.split("T");
  const [year, month, day] = datePart.split("-").map(Number);
  if (!year || !month || !day) return value;

  return DATE_FORMATTER.format(new Date(Date.UTC(year, month - 1, day)));
}

function formatBirthTime(
  value: string | null | undefined,
  known: boolean | null | undefined,
): string {
  if (!known) return "Время не указано";
  return value ? value.slice(0, 5) : "Время не указано";
}

function formatCoordinate(
  value: number,
  positiveLabel: "N" | "E",
  negativeLabel: "S" | "W",
): string {
  return `${Math.abs(value).toFixed(4)}° ${value >= 0 ? positiveLabel : negativeLabel}`;
}

function formatCoordinates(
  lat: number | null | undefined,
  lng: number | null | undefined,
): string {
  if (lat == null || lng == null) return "Координаты не указаны";
  return `${formatCoordinate(lat, "N", "S")} · ${formatCoordinate(lng, "E", "W")}`;
}

function formatDegreeFromParts(
  degree: number | null | undefined,
  minute: number | null | undefined,
): string {
  if (degree == null) return "—";
  return `${Math.floor(degree)}°${Math.floor(minute ?? 0)
    .toString()
    .padStart(2, "0")}'`;
}

function formatDegree(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const normalized = ((value % 30) + 30) % 30;
  let degree = Math.floor(normalized);
  let minute = Math.round((normalized - degree) * 60);
  if (minute === 60) {
    degree = (degree + 1) % 30;
    minute = 0;
  }
  return `${degree}°${minute.toString().padStart(2, "0")}'`;
}

function formatDegreeShort(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(((value % 30) + 30) % 30)}°`;
}

function titleFromPoint(value: string): string {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function pointKey(value: string): string {
  return value.replace(/[\s_-]/g, "").toLowerCase();
}

function pointSymbol(value: string): string {
  const key = value.toLowerCase();
  return (
    PLANET_SYMBOLS[key] ??
    POINT_SYMBOLS[key] ??
    POINT_SYMBOLS[pointKey(value)] ??
    "✦"
  );
}

function aspectDisplayName(value: string): string {
  const key = value.toLowerCase();
  return (
    PLANET_RU[key] ??
    POINT_RU[key] ??
    POINT_RU[pointKey(value)] ??
    titleFromPoint(value)
  );
}

function pluralizeAspects(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return "аспект";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14))
    return "аспекта";
  return "аспектов";
}

function getPlanetData(
  summary: NatalSummaryResponse | undefined,
  full: NatalFullResponse | undefined,
  planet: string,
):
  | { sign?: string | null; sign_ru?: string; sign_degree?: number }
  | undefined {
  return full?.planets?.[planet] ?? summary?.planets?.[planet];
}

function getElementSummary(summary: NatalSummaryResponse | undefined): {
  key: string;
  label: string;
  text: string;
  description: string;
  color: string;
} {
  const signs = [summary?.sun_sign, summary?.moon_sign, summary?.ascendant_sign]
    .map(normalizeSign)
    .filter(Boolean);

  const fallback = ELEMENT_TONE.water;
  if (signs.length === 0) {
    return {
      key: "water",
      label: "Вода",
      text: `Сильная ${fallback.adjective} энергия`,
      description: fallback.description,
      color: fallback.color,
    };
  }

  const ranked = Object.entries(ELEMENTS)
    .map(([key, element]) => ({
      key,
      label: element.label,
      count: signs.filter((sign) => element.signs.includes(sign)).length,
    }))
    .sort((a, b) => b.count - a.count);

  const dominant = ranked[0] ?? { key: "water", label: "Вода" };
  const tone = ELEMENT_TONE[dominant.key] ?? fallback;

  return {
    key: dominant.key,
    label: dominant.label,
    text: `Сильная ${tone.adjective} энергия`,
    description: tone.description,
    color: tone.color,
  };
}

function IconDownload() {
  return (
    <svg width="25" height="25" viewBox="0 0 25 25" fill="none">
      <path
        d="M12.5 4.5v10M8.5 10.5l4 4 4-4M5.5 19.5h14"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconCalendarSmall() {
  return (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none">
      <rect
        x="4"
        y="5"
        width="16"
        height="15"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      <path
        d="M8 3v4M16 3v4M4 10h16"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconClockSmall() {
  return (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.7" />
      <path
        d="M12 7v5l3 2"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconPinSmall() {
  return (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 21s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      <circle cx="12" cy="9" r="2.4" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}

function IconGlobeSmall() {
  return (
    <svg width="21" height="21" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.7" />
      <path
        d="M3.5 12h17M12 3.5c2.1 2.1 3.2 5 3.2 8.5S14.1 18.4 12 20.5c-2.1-2.1-3.2-5-3.2-8.5S9.9 5.6 12 3.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconDropSmall() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <path
        d="M12 3s6 6.8 6 11a6 6 0 0 1-12 0c0-4.2 6-11 6-11Z"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconStarSmall() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <path
        d="m12 3 2.7 5.7 6.3.8-4.6 4.4 1.2 6.1-5.6-3-5.6 3 1.2-6.1L3 9.5l6.3-.8L12 3Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function NatalTopBar() {
  return (
    <header className={styles.topBar}>
      <div className={styles.titleBlock}>
        <h1 className={styles.title}>Натальная карта</h1>
        <div className={styles.titleDivider} aria-hidden="true">
          <svg viewBox="0 0 12 12" fill="currentColor">
            <path d="M6 0 L7.4 4.6 L12 6 L7.4 7.4 L6 12 L4.6 7.4 L0 6 L4.6 4.6 Z" />
          </svg>
        </div>
      </div>
      <div className={styles.headerMoon} aria-label="Луна">
        <span className={styles.headerMoonSurface} aria-hidden="true" />
      </div>
    </header>
  );
}

function NatalTabBar({
  tab,
  onChange,
}: {
  tab: NatalTab;
  onChange: (next: NatalTab) => void;
}) {
  return (
    <div
      className={styles.tabBar}
      role="tablist"
      aria-label="Разделы натальной карты"
    >
      {NATAL_TABS.map((item) => (
        <button
          key={item.key}
          type="button"
          role="tab"
          className={`${styles.tabButton}${tab === item.key ? ` ${styles.tabButtonActive}` : ""}`}
          onClick={() => onChange(item.key)}
          aria-selected={tab === item.key}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

function NatalConstellation({ sign }: { sign?: string | null }) {
  const constellationKey = signKey(sign) || "sagittarius";
  const definition =
    ZODIAC_CONSTELLATIONS[constellationKey] ??
    ZODIAC_CONSTELLATIONS.sagittarius;
  const xs = definition.stars.map(([x]) => x);
  const ys = definition.stars.map(([, y]) => y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const canvas = 200;
  const padding = 36;
  const scale = Math.min(
    (canvas - padding * 2) / Math.max(maxX - minX, 1),
    (canvas - padding * 2) / Math.max(maxY - minY, 1),
  );
  const offsetX = (canvas - (maxX - minX) * scale) / 2 - minX * scale;
  const offsetY = (canvas - (maxY - minY) * scale) / 2 - minY * scale;
  const tx = (x: number) => x * scale + offsetX;
  const ty = (y: number) => y * scale + offsetY;
  const dotGradientId = `natal-constellation-dot-${constellationKey}`;
  const heroGradientId = `natal-constellation-hero-${constellationKey}`;
  const starGradientId = `natal-constellation-star-${constellationKey}`;

  return (
    <svg
      className={styles.constellation}
      viewBox="0 0 200 200"
      fill="none"
      aria-hidden="true"
    >
      <defs>
        <radialGradient id={dotGradientId} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fff5cc" stopOpacity="0.85" />
          <stop offset="40%" stopColor="#e8b860" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#c98a30" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={heroGradientId} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#fff8d8" stopOpacity="1" />
          <stop offset="14%" stopColor="#ffd97a" stopOpacity="0.85" />
          <stop offset="40%" stopColor="#e0a850" stopOpacity="0.4" />
          <stop offset="80%" stopColor="#c98a30" stopOpacity="0.08" />
          <stop offset="100%" stopColor="#c98a30" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={starGradientId} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="1" />
          <stop offset="55%" stopColor="#fff5cc" stopOpacity="1" />
          <stop offset="100%" stopColor="#f8d878" stopOpacity="1" />
        </radialGradient>
      </defs>
      <g className={styles.constellationLines}>
        {definition.lines.map(([from, to], index) => {
          const start = definition.stars[from];
          const end = definition.stars[to];
          if (!start || !end) return null;

          return (
            <line
              key={`${from}-${to}-${index}`}
              x1={tx(start[0])}
              y1={ty(start[1])}
              x2={tx(end[0])}
              y2={ty(end[1])}
            />
          );
        })}
      </g>
      <g className={styles.constellationStars}>
        {definition.stars.map(([x, y, brightness]) => {
          const cx = tx(x);
          const cy = ty(y);
          const isHero = brightness >= 1.25;
          const haloRadius = (isHero ? 8 : 5.5) * brightness;
          const coreRadius = (isHero ? 1.8 : 1.4) * brightness;
          const spikeLength = 9 * brightness;
          const spikeWidth = 0.55;

          return (
            <g
              key={`${x}-${y}-${brightness}`}
              transform={`translate(${cx}, ${cy})`}
            >
              <circle
                r={haloRadius}
                fill={`url(#${isHero ? heroGradientId : dotGradientId})`}
                opacity={isHero ? 0.75 : 1}
              />
              {isHero && (
                <>
                  <path
                    d={`M-${spikeLength},0 L0,-${spikeWidth} L${spikeLength},0 L0,${spikeWidth} Z`}
                    fill="#f8d878"
                    opacity="0.55"
                  />
                  <path
                    d={`M0,-${spikeLength} L${spikeWidth},0 L0,${spikeLength} L-${spikeWidth},0 Z`}
                    fill="#f8d878"
                    opacity="0.55"
                  />
                </>
              )}
              <circle
                r={coreRadius}
                fill={isHero ? `url(#${starGradientId})` : "#fff3c8"}
              />
              <circle r={coreRadius * 0.42} fill="#ffffff" opacity="0.9" />
            </g>
          );
        })}
      </g>
    </svg>
  );
}

function DecorativeOrbit({
  symbols,
  variant,
}: {
  symbols: string[];
  variant: "planets" | "houses";
}) {
  return (
    <div
      className={`${styles.orbitArt} ${
        variant === "planets" ? styles.orbitArtPlanets : styles.orbitArtHouses
      }`}
      aria-hidden="true"
    >
      <div className={styles.orbitCore} />
      {symbols.map((symbol, index) => (
        <span
          key={`${symbol}-${index}`}
          className={styles.orbitGlyph}
          style={
            {
              "--orbit-angle": `${index * (360 / symbols.length)}deg`,
            } as CSSProperties
          }
        >
          {symbol}
        </span>
      ))}
    </div>
  );
}

function NatalKeyChips({
  summary,
  full,
  chartData,
}: {
  summary: NatalSummaryResponse | undefined;
  full: NatalFullResponse | undefined;
  chartData: NatalChartData;
}) {
  const sun = getPlanetData(summary, full, "sun");
  const moon = getPlanetData(summary, full, "moon");
  const ascendantDegree =
    chartData.ascendant.degree != null
      ? formatDegreeFromParts(
          chartData.ascendant.degree,
          chartData.ascendant.minute,
        )
      : "—";

  const ascSign = toZodiacSign(signKey(summary?.ascendant_sign));
  const chips: {
    key: string;
    glyph: React.ReactNode;
    title: string;
    sign: string;
    degree: string;
  }[] = [
    {
      key: "asc",
      glyph: ascSign ? <ZodiacIcon sign={ascSign} size={20} /> : "AC",
      title: "ASC",
      sign: toRu(summary?.ascendant_sign),
      degree: ascendantDegree,
    },
    {
      key: "sun",
      glyph: "☉",
      title: "Sun",
      sign: sun?.sign_ru ?? toRu(sun?.sign ?? summary?.sun_sign),
      degree: formatDegree(sun?.sign_degree),
    },
    {
      key: "moon",
      glyph: "☽",
      title: "Moon",
      sign: moon?.sign_ru ?? toRu(moon?.sign ?? summary?.moon_sign),
      degree: formatDegree(moon?.sign_degree),
    },
  ];

  return (
    <div className={styles.keyChips}>
      {chips.map((chip) => (
        <div key={chip.key} className={styles.keyChip}>
          <span className={styles.keyChipGlyph} aria-hidden="true">
            {chip.glyph}
          </span>
          <span className={styles.keyChipText}>
            <b>{chip.title}</b>
            <span>{chip.sign}</span>
            <small>{chip.degree}</small>
          </span>
        </div>
      ))}
    </div>
  );
}

function NatalHeroCard({
  chartData,
  summary,
  full,
  userName,
}: {
  chartData: NatalChartData;
  summary: NatalSummaryResponse | undefined;
  full: NatalFullResponse | undefined;
  userName?: string | null;
}) {
  const displayName = userName?.trim() || "Моя карта";
  const ascendantSign = summary?.ascendant_sign;
  const sunSign = summary?.sun_sign;
  const subtitleSign = ascendantSign || sunSign;
  const subtitle = ascendantSign
    ? `${toRu(ascendantSign)} восходящий`
    : `${toRu(sunSign)} солнечный знак`;

  return (
    <section className={styles.heroCard} aria-label="Основная натальная карта">
      <div className={styles.heroAura} aria-hidden="true" />
      <NatalConstellation sign={subtitleSign} />

      <div className={styles.heroCopy}>
        <div className={styles.heroKicker}>
          <span aria-hidden="true">✦</span>
          <span>МОЯ КАРТА</span>
          <span aria-hidden="true">✦</span>
        </div>
        <h2 className={styles.personName}>{displayName}</h2>
        <div className={styles.ascLine}>
          <span aria-hidden="true">
            {(() => {
              const s = toZodiacSign(signKey(subtitleSign));
              return s ? <ZodiacIcon sign={s} size={18} /> : "☉";
            })()}
          </span>
          <span>{subtitle}</span>
        </div>
        <p className={styles.quote}>«Рождённый звёздами»</p>
      </div>

      <div className={styles.wheelStage}>
        <NatalChart
          data={{ ...chartData, name: displayName }}
          theme="onyx-gold"
          variant="reference-wheel"
          size={650}
          className={styles.wheel}
        />
      </div>

      <NatalKeyChips summary={summary} full={full} chartData={chartData} />
    </section>
  );
}

function NatalBirthDetails({
  summary,
}: {
  summary: NatalSummaryResponse | undefined;
}) {
  const element = getElementSummary(summary);
  const ascendant = summary?.ascendant_sign
    ? `Восходящий ${toRu(summary.ascendant_sign)}`
    : "Асцендент уточняется";
  const focus =
    FOCUS_PHRASES[normalizeSign(summary?.sun_sign)] ?? "Фокус на личной силе";

  return (
    <section
      className={styles.detailsCard}
      aria-label="Данные рождения и ключевые акценты"
    >
      <div className={styles.birthRows}>
        <div className={styles.birthRow}>
          <IconCalendarSmall />
          <span>{formatBirthDate(summary?.birth_date)}</span>
        </div>
        <div className={styles.birthRow}>
          <IconClockSmall />
          <span>
            {formatBirthTime(summary?.birth_time, summary?.birth_time_known)}
          </span>
        </div>
        <div className={styles.birthRow}>
          <IconPinSmall />
          <span>{summary?.birth_city || "Город не указан"}</span>
        </div>
        <div className={styles.birthRow}>
          <IconGlobeSmall />
          <span>
            {formatCoordinates(summary?.birth_lat, summary?.birth_lng)}
          </span>
        </div>
        <div className={styles.timezone}>
          Часовой пояс: {summary?.birth_tz || "не указан"}
        </div>
      </div>

      <div className={styles.detailsDivider} aria-hidden="true" />

      <div className={styles.highlights}>
        <h3>Ключевые акценты</h3>
        <div className={styles.highlightRow}>
          <span aria-hidden="true">
            {(() => {
              const s = toZodiacSign(signKey(summary?.ascendant_sign));
              return s ? <ZodiacIcon sign={s} size={18} /> : "AC";
            })()}
          </span>
          <p>{ascendant}</p>
        </div>
        <div className={styles.highlightRow} style={{ color: element.color }}>
          <IconDropSmall />
          <p>{element.text}</p>
        </div>
        <div className={styles.highlightRow}>
          <IconStarSmall />
          <p>{focus}</p>
        </div>
      </div>
    </section>
  );
}

function NatalPdfCard({
  hasChart,
  isDownloading,
  error,
  onDownload,
}: {
  hasChart: boolean;
  isDownloading: boolean;
  error: string | null;
  onDownload: () => void;
}) {
  const entitled = useEntitlement("natal_full");
  const price = useProductPrice("natal_full") ?? 149;
  const {
    purchase,
    activating,
    phase,
    error: payError,
  } = usePayment();
  const paying = phase === "opening" || phase === "activating";
  const sendToTelegramChat = Boolean(WebApp.initData);

  const handleClick = async () => {
    if (!hasChart) return;
    if (entitled) {
      onDownload();
      return;
    }
    const ok = await purchase("natal_full");
    if (ok) onDownload();
  };

  const busy = isDownloading || paying;
  let label: string;
  if (!hasChart) {
    label = "Сначала заполните данные рождения";
  } else if (activating) {
    label = "Активируем доступ…";
  } else if (paying) {
    label = "Открываем оплату…";
  } else if (isDownloading) {
    label = "Готовим PDF…";
  } else if (entitled) {
    label = sendToTelegramChat
      ? "Получить полный отчёт в Telegram"
      : "Скачать полный отчёт (PDF)";
  } else {
    label = `Открыть отчёт — ${price} ⭐`;
  }

  return (
    <section className={styles.pdfCard}>
      <motion.button
        type="button"
        className={styles.pdfButton}
        onClick={handleClick}
        disabled={!hasChart || busy}
        aria-busy={busy}
        whileTap={{ scale: busy || !hasChart ? 1 : 0.98 }}
      >
        <IconDownload />
        <span>{label}</span>
      </motion.button>
      {!entitled && hasChart && !paying && (
        <p className={styles.pdfHint}>
          Премиум-доступ ко всей карте + PDF-отчёт. Также входит в Premium-подписку.
        </p>
      )}
      {(error || payError) && (
        <p className={styles.downloadError}>{error ?? payError}</p>
      )}
    </section>
  );
}

function NatalNoChartCard({
  userSign,
  sunSign,
  summary,
}: {
  userSign: (typeof ZODIAC_SIGNS)[number] | undefined;
  sunSign: string | null | undefined;
  summary: NatalSummaryResponse | undefined;
}) {
  return (
    <motion.div
      className={styles.referencePanel}
      initial={false}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className={styles.sectionKicker}>Базовый портрет</div>
      <div className={styles.basicSignRow}>
        <span>
          {userSign ? <ZodiacIcon sign={userSign.value} size={30} /> : "☉"}
        </span>
        <div>
          <h2>{userSign?.label ?? toRu(sunSign)}</h2>
          <p>{userSign?.dates}</p>
        </div>
      </div>
      <p className={styles.panelText}>
        Для полного круга нужны точные дома и положения планет. Проверьте дату,
        время и город рождения в профиле.
      </p>
      {summary?.birth_city && (
        <div className={styles.compactLocation}>
          <IconPinSmall />
          <span>{summary.birth_city}</span>
        </div>
      )}
    </motion.div>
  );
}

function NatalElementsPanel({
  summary,
  slides,
  onSelect,
}: {
  summary: NatalSummaryResponse | undefined;
  slides: NatalInterpretationSlide[];
  onSelect: (selection: NatalDescSelection) => void;
}) {
  const planets = [
    summary?.sun_sign,
    summary?.moon_sign,
    summary?.ascendant_sign,
  ]
    .map(normalizeSign)
    .filter(Boolean);
  const total = Math.max(planets.length, 1);

  const elementCountMap = ELEMENT_ORDER.reduce<Record<string, number>>(
    (acc, key) => {
      acc[key] = planets.filter((p) =>
        ELEMENTS[key].signs.includes(p),
      ).length;
      return acc;
    },
    {},
  );

  return (
    <motion.div
      className={styles.elementsPage}
      initial={false}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className={styles.sectionKicker}>Баланс стихий</div>
      <div className={styles.elementGrid}>
        {ELEMENT_ORDER.map((key) => {
          const element = ELEMENTS[key];
          const count = elementCountMap[key];
          const tone = ELEMENT_TONE[key];
          const meta = ELEMENT_META[key];
          const accent =
            meta?.accent ?? tone?.color ?? ELEMENT_COLORS[key];

          return (
            <button
              type="button"
              key={key}
              className={`${styles.elementCard} ${styles[`elementCard${meta.toneClass.charAt(0).toUpperCase()}${meta.toneClass.slice(1)}`]} ${styles.elementCardButton ?? ""}`}
              style={{ color: accent }}
              onClick={() =>
                onSelect({
                  title: element.label,
                  subtitle: `${meta?.subtitle ?? ""} · ${count} из ${total} в этой стихии`,
                  body:
                    ELEMENT_FALLBACK_DESC[key] ??
                    "Информации об этой стихии пока нет.",
                  accent,
                })
              }
            >
              <span className={styles.elementIcon} aria-hidden="true">
                <CosmicElementOrb element={key as ElementId} size={132} />
              </span>
              <span className={styles.elementText}>
                <b>{element.label}</b>
                <small>{meta?.subtitle}</small>
                <strong>
                  {count} <span>/ {total}</span>
                </strong>
              </span>
            </button>
          );
        })}
      </div>

      {summary?.sun_sign && SIGN_TRAITS[normalizeSign(summary.sun_sign)] && (
        <div className={styles.traitCloud}>
          {SIGN_TRAITS[normalizeSign(summary.sun_sign)].map((trait) => (
            <button
              type="button"
              key={trait}
              className={styles.traitChip ?? ""}
              onClick={() =>
                onSelect({
                  title: trait,
                  subtitle: `Качество знака ${
                    summary.sun_sign
                      ? normalizeSign(summary.sun_sign)
                      : ""
                  }`,
                  body:
                    TRAIT_FALLBACK_DESC[trait] ??
                    "Это качество — типичная черта вашего знака Солнца.",
                })
              }
            >
              {trait}
            </button>
          ))}
        </div>
      )}

      <NatalInterpretationPanel slides={slides} />
    </motion.div>
  );
}

function NatalInterpretationPanel({
  slides,
}: {
  slides: NatalInterpretationSlide[];
}) {
  if (slides.length === 0) return null;

  return (
    <section className={styles.interpretationPanel}>
      <div className={styles.interpretationHeader}>
        <span aria-hidden="true">✦</span>
        <h2>Персональная интерпретация</h2>
        <span aria-hidden="true">✦</span>
      </div>
      <NatalInterpretationSlider slides={slides} />
    </section>
  );
}

function NatalPlanetsPanel({
  full,
  descriptions,
  onSelect,
}: {
  full: NatalFullResponse;
  descriptions: NatalDescriptionsResponse | undefined;
  onSelect: (selection: NatalDescSelection) => void;
}) {
  const visibleRows = PLANET_ROWS.filter((row) => full.planets?.[row.key]);

  return (
    <motion.div
      className={styles.planetsPage}
      initial={false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
    >
      <section className={styles.planetsHero}>
        <div className={styles.panelHeroCopy}>
          <div className={styles.panelEyebrow}>Полная карта</div>
          <h2>{visibleRows.length} планет отображено</h2>
          <p>
            Ваш космический отпечаток — раскройте влияние планет на вашу
            личность и судьбу.
          </p>
        </div>
        <DecorativeOrbit symbols={PLANET_HERO_SYMBOLS} variant="planets" />
      </section>

      <div className={styles.planetList}>
        {visibleRows.map((row) => {
          const planet = full.planets[row.key];
          const accent = row.color ?? PLANET_ACCENTS[row.key] ?? "#ffd476";
          const degText = `${formatDegreeShort(planet.sign_degree)}${
            planet.retrograde ? " ℞" : ""
          }`;
          const desc = descriptions?.planets?.[row.key];
          const subtitle = `${planet.sign_ru} · ${degText} · Дом ${planet.house}`;

          return (
            <button
              type="button"
              key={row.key}
              className={`${styles.planetCard} ${styles.planetCardButton}`}
              style={
                {
                  color: accent,
                  "--planet-rgb": row.rgb,
                } as CSSProperties
              }
              onClick={() =>
                onSelect({
                  title: `${row.name} в ${planet.sign_ru}`,
                  subtitle,
                  symbol: row.symbol,
                  body:
                    desc?.short ?? PLANET_FALLBACK_DESC[row.key] ?? row.desc,
                  accent,
                })
              }
            >
              <span className={styles.planetOrb} aria-hidden="true">
                <PlanetOrb id={row.key} size={88} showGlyph={false} />
              </span>
              <span className={styles.planetCopy}>
                <h3>{row.name}</h3>
                <span className={styles.planetMeta}>
                  <span className={styles.planetMetaSign}>
                    {planet.sign_ru}
                  </span>
                  <span
                    className={styles.planetMetaDeg}
                    style={{ color: accent }}
                  >
                    {degText}
                  </span>
                  <span className={styles.planetMetaDot} aria-hidden="true" />
                  <span className={styles.planetMetaHouse}>
                    Дом {planet.house}
                  </span>
                </span>
                <p>{row.desc}</p>
              </span>
              <span className={styles.planetChev} aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M5 3 L 10 7 L 5 11"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </button>
          );
        })}
      </div>
    </motion.div>
  );
}

function NatalHousesPanel({
  full,
  descriptions,
  onSelect,
}: {
  full: NatalFullResponse;
  descriptions: NatalDescriptionsResponse | undefined;
  onSelect: (selection: NatalDescSelection) => void;
}) {
  return (
    <motion.div
      className={styles.housesPage}
      initial={false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
    >
      <section className={styles.housesHero}>
        <div className={styles.panelHeroCopy}>
          <div className={styles.panelEyebrow}>Куспиды домов</div>
          <h2>12 домов гороскопа</h2>
        </div>
        <DecorativeOrbit symbols={HOUSE_HERO_SYMBOLS} variant="houses" />
      </section>

      <div className={styles.housesGrid}>
        {full.houses.map((house) => {
          const houseSignKey = signKey(house.sign);
          const signRu =
            SIGN_EN_TO_RU[normalizeSign(house.sign)] ??
            house.sign_ru ??
            house.sign;
          const axisLabel = HOUSE_AXIS_LABELS[house.number];
          const glyph = ZODIAC_GLYPHS[houseSignKey] ?? "✦";
          const houseZodiac = toZodiacSign(houseSignKey);
          const tone = ZODIAC_TONES[houseSignKey] ?? "gold";
          const desc = descriptions?.houses?.[String(house.number)];
          const subtitleParts = [signRu, formatDegree(house.degree)];
          if (axisLabel) subtitleParts.push(axisLabel);

          return (
            <button
              type="button"
              key={house.number}
              className={`${styles.houseCard} ${styles.houseCardButton} ${
                axisLabel ? styles.houseCardAxis : ""
              }`}
              data-tone={tone}
              onClick={() =>
                onSelect({
                  title: `Дом ${house.number} — ${signRu}`,
                  subtitle: subtitleParts.join(" · "),
                  symbol: glyph,
                  body:
                    desc?.short ??
                    HOUSE_FALLBACK_DESC[String(house.number)] ??
                    null,
                })
              }
            >
              <span className={styles.houseNumber}>{house.number}</span>
              <span className={styles.houseGlyph} aria-hidden="true">
                {houseZodiac ? <ZodiacIcon sign={houseZodiac} size={20} /> : glyph}
              </span>
              <span className={styles.houseCopy}>
                <b>{signRu}</b>
                <small>{formatDegree(house.degree)}</small>
                {axisLabel && <em>{axisLabel}</em>}
              </span>
              <span className={styles.houseChev} aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M5 3 L 10 7 L 5 11"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </button>
          );
        })}
      </div>
    </motion.div>
  );
}

function NatalAspectsPanel({
  full,
  descriptions,
  onSelect,
}: {
  full: NatalFullResponse;
  descriptions: NatalDescriptionsResponse | undefined;
  onSelect: (selection: NatalDescSelection) => void;
}) {
  return (
    <motion.section
      className={styles.aspectsPage}
      initial={false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
    >
      <div className={styles.aspectsHeader}>
        <h2>
          <span aria-hidden="true">✷</span>
          Аспекты
          <span aria-hidden="true">✧</span>
        </h2>
        <p>Гармония и напряжение между планетами</p>
      </div>

      {full.aspects.length === 0 && (
        <div className={styles.loadingState}>Значимые аспекты не найдены.</div>
      )}

      <div className={styles.aspectGroups}>
        {ASPECT_ORDER.map((type) => {
          const group = full.aspects.filter((aspect) => aspect.aspect === type);
          const meta = ASPECT_META[type];
          if (!meta || group.length === 0) return null;

          const buildAspectsBody = () => {
            const intro = ASPECT_FALLBACK_DESC[type] ?? "";
            const blocks: string[] = [];
            if (intro) blocks.push(intro);

            for (const aspect of group) {
              const p1 = aspect.p1.toLowerCase();
              const p2 = aspect.p2.toLowerCase();
              const desc = descriptions?.aspects?.find(
                (a) =>
                  a.type === aspect.aspect &&
                  ((a.p1 === p1 && a.p2 === p2) ||
                    (a.p1 === p2 && a.p2 === p1)),
              );
              const name1 = aspectDisplayName(aspect.p1);
              const name2 = aspectDisplayName(aspect.p2);
              const heading = `**${name1} ${meta.symbol} ${name2} · орб ${aspect.orb.toFixed(1)}°**`;
              const hint =
                ASPECT_PAIR_FALLBACK_HINT[type] ??
                "взаимодействуют между собой";
              const fallback = `${name1} и ${name2} ${hint}. Подробнее эта пара раскроется в полном PDF-отчёте.`;
              const text = desc?.short ?? fallback;
              blocks.push(`${heading}\n\n${text}`);
            }

            return blocks.join("\n\n").trim() || null;
          };

          const subtitle = `${group.length} ${pluralizeAspects(group.length)}`;

          return (
            <button
              type="button"
              key={type}
              className={`${styles.aspectGroup} ${styles.aspectGroupButton}`}
              style={{ color: meta.accent }}
              onClick={() =>
                onSelect({
                  title: meta.name,
                  subtitle,
                  symbol: meta.symbol,
                  body: buildAspectsBody(),
                  accent: meta.accent,
                })
              }
            >
              <span className={styles.aspectGroupSparkle} aria-hidden="true">
                ✦
              </span>
              <span className={styles.aspectIcon} aria-hidden="true">
                <AspectOrb
                  type={type}
                  symbol={meta.symbol}
                  color={meta.accent}
                  size={92}
                />
              </span>
              <span className={styles.aspectContent}>
                <h3>{meta.name}</h3>
                <span className={styles.aspectRows}>
                  {group.map((aspect, index) => {
                    const name1 = aspectDisplayName(aspect.p1);
                    const name2 = aspectDisplayName(aspect.p2);
                    return (
                      <span
                        key={`${aspect.p1}-${aspect.p2}-${index}`}
                        className={styles.aspectRow}
                        style={{ color: meta.accent }}
                      >
                        <span className={styles.aspectPair}>
                          <span className={styles.aspectPoint}>
                            <i aria-hidden="true">{pointSymbol(aspect.p1)}</i>
                            {name1}
                          </span>
                          <b>{meta.symbol}</b>
                          <span className={styles.aspectPoint}>
                            <i aria-hidden="true">{pointSymbol(aspect.p2)}</i>
                            {name2}
                          </span>
                        </span>
                        <span className={styles.aspectOrbValue}>
                          {aspect.orb.toFixed(1)}°
                        </span>
                      </span>
                    );
                  })}
                </span>
              </span>
              <span className={styles.aspectGroupChev} aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M5 3 L 10 7 L 5 11"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
            </button>
          );
        })}
      </div>
    </motion.section>
  );
}

export function Natal() {
  const { user, setScreen } = useAppStore();
  const hasBirthData = !!user?.birth_city;
  const [tab, setTab] = useState<NatalTab>("circle");
  const [isPdfDownloading, setIsPdfDownloading] = useState(false);
  const [pdfDownloadError, setPdfDownloadError] = useState<string | null>(null);

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["natal-summary"],
    queryFn: natalApi.getSummary,
    enabled: hasBirthData,
    staleTime: 1000 * 60 * 10,
  });

  const { data: full, isLoading: fullLoading } = useQuery({
    queryKey: ["natal-full"],
    queryFn: natalApi.getFull,
    enabled: hasBirthData && (summary?.has_chart ?? false),
    staleTime: 1000 * 60 * 60,
  });

  const isFullPanel =
    tab === "planets" || tab === "houses" || tab === "aspects";
  const { data: descriptions, isLoading: descriptionsLoading } = useQuery({
    queryKey: ["natal-descriptions"],
    queryFn: natalApi.getDescriptions,
    enabled: hasBirthData && (summary?.has_chart ?? false) && isFullPanel,
    staleTime: 1000 * 60 * 60 * 24,
  });

  const [selectedDesc, setSelectedDesc] = useState<NatalDescSelection | null>(
    null,
  );

  const openBigThreeSheet = (kind: "sun" | "moon" | "ascendant") => {
    const BIG_THREE_META: Record<
      typeof kind,
      { title: string; symbol: string; accent: string }
    > = {
      sun: { title: "Солнце", symbol: "☉", accent: "var(--gold)" },
      moon: { title: "Луна", symbol: "☽", accent: "#c6d5e8" },
      ascendant: { title: "Асцендент", symbol: "↗", accent: "#e8b4a8" },
    };
    const meta = BIG_THREE_META[kind];
    const sign =
      kind === "sun"
        ? summary?.sun_sign
        : kind === "moon"
          ? summary?.moon_sign
          : summary?.ascendant_sign;
    const planetKey = kind === "ascendant" ? "ascendant" : kind;
    const desc = descriptions?.planets?.[planetKey];
    const body =
      (desc as { short?: string; full?: string } | string | undefined) &&
      typeof desc === "object"
        ? ((desc as { full?: string; short?: string }).full ??
          (desc as { full?: string; short?: string }).short ??
          null)
        : ((desc as unknown as string | undefined) ??
          PLANET_FALLBACK_DESC[planetKey] ??
          null);
    setSelectedDesc({
      title: meta.title,
      subtitle: sign ?? undefined,
      symbol: meta.symbol,
      body,
      accent: meta.accent,
    });
  };

  const openDominantElement = (element: NatalElementKey) => {
    const ELEMENT_TITLE: Record<NatalElementKey, string> = {
      fire: "Огонь",
      earth: "Земля",
      air: "Воздух",
      water: "Вода",
    };
    setSelectedDesc({
      title: ELEMENT_TITLE[element],
      symbol: "✦",
      body: ELEMENT_FALLBACK_DESC[element] ?? null,
    });
  };

  const openDominantModality = () => {
    if (!summary?.dominants) return;
    const mod = summary.dominants.modalities;
    setSelectedDesc({
      title: `${mod.dominant_ru} модальность`,
      subtitle: "Как вы действуете и проявляетесь",
      symbol: "✦",
      body:
        mod.dominant === "cardinal"
          ? "Кардинальная модальность — про инициативу и старт. Вы быстро берётесь за новое, любите задавать темп и плохо переносите простой. Сильная сторона — лидерство; зона роста — доводить до конца, не бросать на середине."
          : mod.dominant === "fixed"
            ? "Фиксированная модальность — про устойчивость и глубину. Вы держите курс, доводите начатое, цените стабильность. Сильная сторона — надёжность; зона роста — гибкость, способность вовремя сменить тактику."
            : "Мутабельная модальность — про адаптацию и переходы. Вы легко перестраиваетесь, ловите контекст, видите нюансы. Сильная сторона — гибкость; зона роста — выбрать одно направление и не распыляться.",
    });
  };

  const openDominantPlanet = () => {
    if (!summary?.dominants) return;
    const planet = summary.dominants.planet;
    setSelectedDesc({
      title: `Доминирующая планета — ${planet.planet_ru}`,
      subtitle: planet.reason,
      symbol: "✦",
      body:
        PLANET_FALLBACK_DESC[planet.planet] ??
        "Эта планета сильнее всего звучит в вашей карте: её темы будут возвращаться к вам в разных формах.",
    });
  };

  const openKeyAspect = (a: NatalKeyAspect) => {
    const aspectType = (a.aspect ?? "").toLowerCase();
    setSelectedDesc({
      title: `${a.p1} ${aspectType} ${a.p2}`,
      subtitle:
        typeof a.orb === "number" ? `Орб ${a.orb.toFixed(1)}°` : undefined,
      symbol: "✦",
      body:
        ASPECT_FALLBACK_DESC[aspectType] ??
        ASPECT_PAIR_FALLBACK_HINT[aspectType] ??
        null,
    });
  };

  const sunSign = summary?.sun_sign ?? user?.sun_sign;
  const userSign = ZODIAC_SIGNS.find((s) => s.value === sunSign);
  const chartData = useMemo(
    () => (summary ? toNatalChartData(summary) : null),
    [summary],
  );
  const interpretationSlides = useMemo<NatalInterpretationSlide[]>(() => {
    if (!full) return [];

    const readingSlides = full.reading
      ? parseReadingSections(full.reading).map((section, index) => {
          const title = section.title || "Вступление";
          return {
            id: `reading-${index}`,
            label: title,
            title,
            body: section.body,
          };
        })
      : [];

    const planetSlides =
      full.interpretations?.map((interp, index) => {
        const symbol = PLANET_SYMBOLS[interp.planet] ?? "✦";
        const planet = PLANET_RU[interp.planet] ?? interp.planet;
        const category = CATEGORY_RU[interp.category] ?? interp.category;
        const title = `${symbol} ${planet} · ${category}`;

        return {
          id: `interp-${interp.planet}-${interp.category}-${index}`,
          label: title,
          title,
          body: interp.text,
        };
      }) ?? [];

    return [...readingSlides, ...planetSlides].filter((slide) =>
      slide.body.trim(),
    );
  }, [full]);

  const handlePdfDownload = async () => {
    if (isPdfDownloading) return;

    setIsPdfDownloading(true);
    setPdfDownloadError(null);
    try {
      await natalApi.downloadPdf();
    } catch (error) {
      setPdfDownloadError(getPdfDownloadError(error));
    } finally {
      setIsPdfDownloading(false);
    }
  };

  const renderFullPanel = () => {
    if (fullLoading) {
      return (
        <motion.div
          className={styles.referencePanel}
          initial={false}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className={styles.loadingState}>Вычисление полной карты...</div>
        </motion.div>
      );
    }

    if (!full) {
      return (
        <motion.div
          className={styles.referencePanel}
          initial={false}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className={styles.loadingState}>
            Нет данных — проверьте дату, время и город рождения.
          </div>
        </motion.div>
      );
    }

    return (
      <>
        {tab === "planets" && (
          <>
            <HeroInfo info={summary?.hero_info?.planets} eyebrow="Планеты" />
            <NatalPlanetsPanel
              full={full}
              descriptions={descriptions}
              onSelect={setSelectedDesc}
            />
          </>
        )}
        {tab === "houses" && (
          <>
            <HeroInfo info={summary?.hero_info?.houses} eyebrow="Дома" />
            <NatalHousesPanel
              full={full}
              descriptions={descriptions}
              onSelect={setSelectedDesc}
            />
          </>
        )}
        {tab === "aspects" && (
          <>
            <HeroInfo info={summary?.hero_info?.aspects} eyebrow="Аспекты" />
            {summary?.key_aspects && summary.key_aspects.length > 0 && (
              <KeyAspectsList
                aspects={summary.key_aspects}
                onOpenAspect={openKeyAspect}
              />
            )}
            <NatalAspectsPanel
              full={full}
              descriptions={descriptions}
              onSelect={setSelectedDesc}
            />
          </>
        )}
      </>
    );
  };

  const renderTabContent = () => {
    if (summaryLoading) {
      return (
        <div className={styles.skeletonPanel}>
          <NatalBasicSkeleton />
        </div>
      );
    }

    if (tab === "circle") {
      return (
        <>
          {chartData ? (
            <motion.div
              initial={false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.42, ease: "easeOut" }}
            >
              <NatalHeroCard
                chartData={chartData}
                summary={summary}
                full={full}
                userName={user?.name}
              />
            </motion.div>
          ) : (
            <NatalNoChartCard
              userSign={userSign}
              sunSign={sunSign}
              summary={summary}
            />
          )}

          {summary?.has_chart && (
            <BigThreeBlock
              summary={summary}
              onOpenSheet={openBigThreeSheet}
              onOpenProfile={() => setScreen("profile")}
            />
          )}

          <NatalBirthDetails summary={summary} />
          <NatalPdfCard
            hasChart={summary?.has_chart ?? false}
            isDownloading={isPdfDownloading}
            error={pdfDownloadError}
            onDownload={handlePdfDownload}
          />
        </>
      );
    }

    if (tab === "elements") {
      return (
        <>
          <HeroInfo info={summary?.hero_info?.elements} eyebrow="Стихии" />
          {summary?.dominants && (
            <DominantsBlock
              dominants={summary.dominants}
              onOpenElement={openDominantElement}
              onOpenModality={openDominantModality}
              onOpenPlanet={openDominantPlanet}
            />
          )}
          <NatalElementsPanel
            summary={summary}
            slides={interpretationSlides}
            onSelect={setSelectedDesc}
          />
          <NatalPdfCard
            hasChart={summary?.has_chart ?? false}
            isDownloading={isPdfDownloading}
            error={pdfDownloadError}
            onDownload={handlePdfDownload}
          />
        </>
      );
    }

    return (
      <>
        {renderFullPanel()}
        <NatalPdfCard
          hasChart={summary?.has_chart ?? false}
          isDownloading={isPdfDownloading}
          error={pdfDownloadError}
          onDownload={handlePdfDownload}
        />
      </>
    );
  };

  return (
    <div className={`screen natal-screen ${styles.screen}`}>
      <div className={styles.sky} aria-hidden="true" />

      <div className={styles.content}>
        <NatalTopBar />

        {!hasBirthData ? (
          <motion.div
            className={styles.emptyState}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className={styles.emptyGlyph} aria-hidden="true">
              <NatalConstellation />
              <span>☉</span>
            </div>
            <h2>Добавьте данные рождения</h2>
            <p>
              Для расчёта натальной карты нужны дата, время и город рождения.
            </p>
            <button
              type="button"
              className={styles.primaryButton}
              onClick={() => setScreen("profile")}
            >
              Указать данные
            </button>
          </motion.div>
        ) : (
          <>
            <NatalTabBar tab={tab} onChange={setTab} />
            <div className={styles.tabContent}>{renderTabContent()}</div>
          </>
        )}
      </div>

      <NatalDescriptionSheet
        open={selectedDesc !== null}
        title={selectedDesc?.title ?? ""}
        subtitle={selectedDesc?.subtitle}
        symbol={selectedDesc?.symbol}
        body={selectedDesc?.body ?? null}
        accent={selectedDesc?.accent}
        isLoading={
          selectedDesc !== null && !selectedDesc.body && descriptionsLoading
        }
        onClose={() => setSelectedDesc(null)}
      />
    </div>
  );
}
