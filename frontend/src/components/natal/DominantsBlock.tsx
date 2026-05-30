import { motion } from "framer-motion";
import type { NatalDominants, NatalElementKey } from "@/types";
import { ElementsRing, ELEMENT_RING_COLORS } from "./ElementsRing";
import { ModalitiesBars } from "./ModalitiesBars";

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
};

const ELEMENT_LABEL: Record<NatalElementKey, string> = {
  fire: "Огонь",
  earth: "Земля",
  air: "Воздух",
  water: "Вода",
};

const ELEMENT_ORDER: NatalElementKey[] = ["fire", "earth", "air", "water"];

interface DominantsBlockProps {
  dominants: NatalDominants;
  onOpenElement: (element: NatalElementKey) => void;
  onOpenModality: () => void;
  onOpenPlanet: () => void;
}

export function DominantsBlock({
  dominants,
  onOpenElement,
  onOpenModality,
  onOpenPlanet,
}: DominantsBlockProps) {
  const el = dominants.elements;
  const total = el.fire + el.earth + el.air + el.water || 1;
  const dominantPercent = Math.round((el[el.dominant] / total) * 100);

  const planet = dominants.planet;
  const planetGlyph = PLANET_GLYPH[planet.planet] ?? "●";

  return (
    <div className="natal-dominants">
      <motion.div
        className="natal-dominants__card"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <div className="natal-dominants__title">Баланс стихий</div>
        <ElementsRing
          fire={el.fire}
          earth={el.earth}
          air={el.air}
          water={el.water}
          dominantLabel={el.dominant_ru}
          dominantPercent={dominantPercent}
          onSegmentClick={onOpenElement}
        />
        <div className="natal-dominants__legend">
          {ELEMENT_ORDER.map((key) => {
            const value = el[key];
            const pct = Math.round((value / total) * 100);
            return (
              <button
                key={key}
                type="button"
                className="natal-dominants__legend-item"
                onClick={() => onOpenElement(key)}
              >
                <span
                  className="natal-dominants__legend-dot"
                  style={{ background: ELEMENT_RING_COLORS[key] }}
                />
                <span className="natal-dominants__legend-label">
                  {ELEMENT_LABEL[key]}
                </span>
                <span className="natal-dominants__legend-pct">{pct}%</span>
              </button>
            );
          })}
        </div>
        {el.deficient_ru && (
          <div className="natal-dominants__note">
            Слабо выражено: {el.deficient_ru.toLowerCase()}
          </div>
        )}
      </motion.div>

      <motion.div
        className="natal-dominants__card"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.08 }}
      >
        <ModalitiesBars
          modalities={dominants.modalities}
          onSelect={onOpenModality}
        />
      </motion.div>

      <motion.button
        type="button"
        className="natal-dominants__card natal-dominants__planet"
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.16 }}
        onClick={onOpenPlanet}
      >
        <div className="natal-dominants__title">Ваша доминирующая планета</div>
        <div className="natal-dominants__planet-row">
          <span className="natal-dominants__planet-glyph">{planetGlyph}</span>
          <div className="natal-dominants__planet-col">
            <span className="natal-dominants__planet-name">
              {planet.planet_ru}
            </span>
            <span className="natal-dominants__planet-reason">
              {planet.reason}
            </span>
          </div>
        </div>
      </motion.button>
    </div>
  );
}
