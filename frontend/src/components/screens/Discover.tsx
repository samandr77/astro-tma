import { useState } from "react";
import { motion } from "framer-motion";
import { useAppStore } from "@/stores/app";
import { useHaptic } from "@/hooks/useTelegram";

interface PracticeCard {
  label: string;
  desc: string;
  icon: JSX.Element;
  screen?: string;
  locked?: boolean;
  gradient: string;
  iconColor: string;
}

const SECTIONS: { title: string; cards: PracticeCard[] }[] = [
  {
    title: "Карты",
    cards: [
      {
        label: "Таро",
        desc: "Расклады и предсказания",
        screen: "tarot",
        gradient:
          "linear-gradient(135deg, rgba(201,168,76,0.12) 0%, rgba(201,168,76,0.03) 100%)",
        iconColor: "#c9a84c",
        icon: (
          <svg
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="5" y="2" width="12" height="18" rx="2" />
            <rect x="11" y="8" width="12" height="18" rx="2" />
            <line x1="8" y1="7" x2="14" y2="7" />
            <line x1="8" y1="11" x2="14" y2="11" />
          </svg>
        ),
      },
      {
        label: "МАК-карты",
        desc: "Метафорические образы",
        screen: "mac",
        gradient:
          "linear-gradient(135deg, rgba(160,125,232,0.12) 0%, rgba(160,125,232,0.03) 100%)",
        iconColor: "#a07de8",
        icon: (
          <svg
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="3" y="3" width="22" height="22" rx="4" />
            <circle cx="14" cy="14" r="6" />
            <circle cx="14" cy="14" r="2.5" />
            <line x1="14" y1="3" x2="14" y2="8" />
            <line x1="14" y1="20" x2="14" y2="25" />
            <line x1="3" y1="14" x2="8" y2="14" />
            <line x1="20" y1="14" x2="25" y2="14" />
          </svg>
        ),
      },
      {
        label: "Матрица Судьбы",
        desc: "Расшифровка по дате рождения",
        screen: "destiny_matrix_info",
        gradient:
          "linear-gradient(135deg, rgba(232,200,98,0.14) 0%, rgba(232,200,98,0.03) 100%)",
        iconColor: "#e8c862",
        icon: (
          <svg
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            {/* Octagram = big diamond ⟂ small square (rotated 45°) */}
            <path d="M14 3l11 11-11 11L3 14z" />
            <path d="M5.5 5.5l17 17M22.5 5.5l-17 17" />
            <circle cx="14" cy="14" r="2" />
          </svg>
        ),
      },
    ],
  },
  {
    title: "Отношения",
    cards: [
      {
        label: "Синастрия",
        desc: "Карта отношений двоих",
        screen: "synastry",
        gradient:
          "linear-gradient(135deg, rgba(232,201,126,0.08) 0%, rgba(232,201,126,0.02) 100%)",
        iconColor: "#e8c97e",
        icon: (
          <svg
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 24S4 17.5 4 10.5a5.5 5.5 0 0111 0 5.5 5.5 0 0111 0C26 17.5 14 24 14 24z" />
          </svg>
        ),
      },
    ],
  },
  {
    title: "Луна и циклы",
    cards: [
      {
        label: "Лунный календарь",
        desc: "Фазы и ритмы месяца",
        screen: "moon",
        gradient:
          "linear-gradient(135deg, rgba(197,184,240,0.1) 0%, rgba(100,90,160,0.06) 100%)",
        iconColor: "#c5b8f0",
        icon: (
          <svg
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M22 17A10 10 0 0111 6a10 10 0 100 22 10 10 0 0011-11z" />
          </svg>
        ),
      },
      {
        label: "Транзиты",
        desc: "Планеты прямо сейчас",
        screen: "transits",
        gradient:
          "linear-gradient(135deg, rgba(158,154,181,0.1) 0%, rgba(158,154,181,0.02) 100%)",
        iconColor: "#9e9ab5",
        icon: (
          <svg
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="14" cy="14" r="11" />
            <circle cx="14" cy="14" r="6" />
            <circle cx="14" cy="14" r="2" />
            <line x1="14" y1="3" x2="14" y2="8" />
            <line x1="14" y1="20" x2="14" y2="25" />
            <line x1="3" y1="14" x2="8" y2="14" />
            <line x1="20" y1="14" x2="25" y2="14" />
          </svg>
        ),
      },
    ],
  },
  {
    title: "Знания",
    cards: [
      {
        label: "Астро-новости",
        desc: "События и прогнозы",
        screen: "news",
        gradient:
          "linear-gradient(135deg, rgba(139,200,155,0.1) 0%, rgba(139,200,155,0.02) 100%)",
        iconColor: "#8bc89b",
        icon: (
          <svg
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="3" y="5" width="22" height="18" rx="3" />
            <line x1="8" y1="11" x2="20" y2="11" />
            <line x1="8" y1="16" x2="15" y2="16" />
            <circle
              cx="22"
              cy="7"
              r="3"
              fill="rgba(201,168,76,0.5)"
              stroke="none"
            />
          </svg>
        ),
      },
      {
        label: "Глоссарий",
        desc: "Термины астрологии",
        screen: "glossary",
        gradient:
          "linear-gradient(135deg, rgba(126,200,227,0.1) 0%, rgba(126,200,227,0.02) 100%)",
        iconColor: "#7ec8e3",
        icon: (
          <svg
            width="28"
            height="28"
            viewBox="0 0 28 28"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M5 23V6a3 3 0 013-3h15v16H8a3 3 0 000 6h15" />
            <line x1="10" y1="9" x2="18" y2="9" />
            <line x1="10" y1="14" x2="18" y2="14" />
          </svg>
        ),
      },
    ],
  },
];

export function Discover() {
  const { setScreen } = useAppStore();
  const { impact } = useHaptic();
  const [shaking, setShaking] = useState<string | null>(null);

  const navigate = (screen: string) => {
    impact("light");
    setScreen(screen as any);
  };

  const handleLockedTap = (label: string) => {
    impact("light");
    setShaking(label);
    setTimeout(() => setShaking(null), 500);
  };

  return (
    <div className="screen discover-screen">
      <div className="screen-header">
        <h2 className="screen-title">Практики</h2>
      </div>

      <div className="screen-content">
        {SECTIONS.map((section, si) => (
          <div key={section.title} className="discover-section">
            <h3 className="discover-section__title">{section.title}</h3>
            <div className="discover-grid">
              {section.cards.map((card, ci) => (
                <motion.button
                  key={card.label}
                  className={`practice-card${card.locked ? " practice-card--locked" : ""}`}
                  style={{ background: card.gradient }}
                  onClick={() =>
                    card.screen && !card.locked
                      ? navigate(card.screen)
                      : handleLockedTap(card.label)
                  }
                  whileTap={!card.locked ? { scale: 0.95 } : undefined}
                  initial={false}
                  animate={
                    shaking === card.label
                      ? { x: [0, -6, 6, -5, 5, -3, 3, 0], opacity: 1, y: 0 }
                      : { x: 0, opacity: 1, y: 0 }
                  }
                  transition={
                    shaking === card.label
                      ? { duration: 0.4, ease: "easeInOut" }
                      : {
                          opacity: {
                            duration: 0.3,
                            delay: (si * 2 + ci) * 0.05,
                          },
                          y: { duration: 0.3, delay: (si * 2 + ci) * 0.05 },
                        }
                  }
                >
                  <div
                    className="practice-card__icon"
                    style={{ color: card.iconColor }}
                  >
                    {card.icon}
                  </div>
                  <div className="practice-card__label">{card.label}</div>
                  <div className="practice-card__desc">{card.desc}</div>
                  {card.locked && (
                    <div className="practice-card__badge">
                      <svg
                        width="9"
                        height="11"
                        viewBox="0 0 9 11"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.3"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <rect x="1" y="4.5" width="7" height="6" rx="1.5" />
                        <path d="M2.5 4.5V3a2 2 0 0 1 4 0v1.5" />
                      </svg>
                      Скоро
                    </div>
                  )}
                </motion.button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
