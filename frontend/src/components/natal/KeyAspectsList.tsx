import { motion } from "framer-motion";
import type { NatalKeyAspect } from "@/types";

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
  mc: "MC",
};

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
  ascendant: "Асцендент",
  mc: "MC",
};

const ASPECT_SYMBOL: Record<string, string> = {
  conjunction: "☌",
  trine: "△",
  sextile: "⚹",
  square: "□",
  opposition: "☍",
  quincunx: "⚻",
};

const ASPECT_RU: Record<string, string> = {
  conjunction: "соединение",
  trine: "трин",
  sextile: "секстиль",
  square: "квадрат",
  opposition: "оппозиция",
  quincunx: "квинконс",
};

const ASPECT_COLOR: Record<string, string> = {
  conjunction: "#e8c97e",
  trine: "#8bc89b",
  sextile: "#7ec8e3",
  square: "#e88b8b",
  opposition: "#c58be8",
  quincunx: "#9e9ab5",
};

interface KeyAspectsListProps {
  aspects: NatalKeyAspect[];
  onOpenAspect: (aspect: NatalKeyAspect) => void;
}

export function KeyAspectsList({ aspects, onOpenAspect }: KeyAspectsListProps) {
  if (!aspects || aspects.length === 0) return null;

  return (
    <div className="natal-key-aspects">
      <div className="natal-key-aspects__title">
        <span className="natal-key-aspects__star">✦</span>
        Ключевые аспекты
      </div>
      <div className="natal-key-aspects__list">
        {aspects.map((a, idx) => {
          const p1Key = (a.p1 || "").toLowerCase();
          const p2Key = (a.p2 || "").toLowerCase();
          const asp = (a.aspect || "").toLowerCase();
          const color = ASPECT_COLOR[asp] ?? "var(--text-dim)";
          return (
            <motion.button
              key={`${a.p1}-${a.p2}-${a.aspect}-${idx}`}
              type="button"
              className="natal-key-aspects__row"
              style={{ borderLeftColor: color }}
              onClick={() => onOpenAspect(a)}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05, duration: 0.25 }}
            >
              <span className="natal-key-aspects__planets">
                <span>{PLANET_GLYPH[p1Key] ?? "●"}</span>
                <span style={{ color }}>{ASPECT_SYMBOL[asp] ?? "·"}</span>
                <span>{PLANET_GLYPH[p2Key] ?? "●"}</span>
              </span>
              <span className="natal-key-aspects__title-text">
                {PLANET_RU[p1Key] ?? a.p1} {ASPECT_RU[asp] ?? a.aspect}{" "}
                {PLANET_RU[p2Key] ?? a.p2}
              </span>
              <span className="natal-key-aspects__orb">
                {typeof a.orb === "number" ? `${a.orb.toFixed(1)}°` : ""}
              </span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
