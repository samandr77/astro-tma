/**
 * Synastry bi-wheel — two natal charts overlaid in concentric rings.
 *
 * Outermost: zodiac ring with sign glyphs.
 * Middle ring: partner B's planets.
 * Inner ring: partner A's planets.
 * Center: aspect lines colored by aspect type.
 *
 * Pure presentational: takes pre-computed planet/aspect data, renders SVG.
 * Sized by `size` prop (rendered as a square). Designed for the celestial
 * theme — black background, gold strokes.
 */
import { zodiacIconUrl } from "@/components/ui/ZodiacIcon";
import type { ZodiacSign } from "@/components/NatalChart/types";
import type {
  SynastryAspectOut,
  SynastryHouseInfo,
  SynastryPlanetInfo,
} from "@/types";

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
  chiron: "⚷",
  true_node: "☊",
  mean_node: "☊",
  lilith: "⚸",
};

const ZODIAC_ORDER = [
  "aries",
  "taurus",
  "gemini",
  "cancer",
  "leo",
  "virgo",
  "libra",
  "scorpio",
  "sagittarius",
  "capricorn",
  "aquarius",
  "pisces",
];

const ASPECT_COLOR: Record<string, string> = {
  conjunction: "rgba(232, 200, 98, 0.85)",
  trine: "rgba(139, 200, 155, 0.7)",
  sextile: "rgba(126, 200, 227, 0.7)",
  square: "rgba(232, 139, 139, 0.65)",
  opposition: "rgba(197, 139, 232, 0.65)",
};

const ASPECT_DASH: Record<string, string> = {
  conjunction: "0",
  trine: "0",
  sextile: "0",
  square: "4 4",
  opposition: "6 4",
};

interface Props {
  planetsA: SynastryPlanetInfo[];
  planetsB: SynastryPlanetInfo[];
  housesA?: SynastryHouseInfo[];
  aspects: SynastryAspectOut[];
  size?: number;
  initiatorName?: string | null;
  partnerName?: string | null;
}

const VIEW = 600;
const CX = VIEW / 2;
const CY = VIEW / 2;

const R_OUTER = 280;        // outer edge of zodiac ring
const R_ZODIAC = 250;       // inner edge of zodiac ring (where signs sit)
const R_HOUSE = 232;        // house cusp ring
const R_PLANET_B = 200;     // partner B (outer)
const R_PLANET_A = 158;     // partner A (inner)
const R_ASPECT = 132;       // aspect lines bounded inside this radius

/** Astrological angle convention: 0° Aries on the left, going CCW.
 * SVG y goes down, so flip to keep "above" on top of screen. */
function polar(deg: number, r: number): { x: number; y: number } {
  const rad = ((180 - deg) * Math.PI) / 180;
  return { x: CX + r * Math.cos(rad), y: CY + r * Math.sin(rad) };
}

/** Spread overlapping planet glyphs on a ring by nudging them apart along
 * the ring. Returns adjusted angle for each input planet. */
function spreadGlyphs(planets: SynastryPlanetInfo[], minGap = 7): number[] {
  if (!planets.length) return [];
  const sorted = planets
    .map((p, i) => ({ idx: i, deg: p.degree }))
    .sort((a, b) => a.deg - b.deg);

  const adjusted = sorted.map((s) => ({ ...s }));
  // Forward pass — push later items if too close
  for (let i = 1; i < adjusted.length; i++) {
    const prev = adjusted[i - 1];
    if (adjusted[i].deg - prev.deg < minGap) {
      adjusted[i].deg = prev.deg + minGap;
    }
  }
  // Wrap check between last and first
  const wrap = adjusted[0].deg + 360 - adjusted[adjusted.length - 1].deg;
  if (wrap < minGap && adjusted.length > 1) {
    adjusted[0].deg = adjusted[adjusted.length - 1].deg + minGap - 360;
  }

  const out = new Array<number>(planets.length);
  adjusted.forEach((s) => {
    out[s.idx] = ((s.deg % 360) + 360) % 360;
  });
  return out;
}

export function SynastryBiWheel({
  planetsA,
  planetsB,
  housesA,
  aspects,
  size = 360,
  initiatorName,
  partnerName,
}: Props) {
  const adjustedA = spreadGlyphs(planetsA);
  const adjustedB = spreadGlyphs(planetsB);

  // Aspect lines: from A's planet (inner) to B's planet (outer)
  const aspectLines = aspects
    .map((a) => {
      const idxA = planetsA.findIndex(
        (p) => p.name.toLowerCase() === a.p1_name.toLowerCase(),
      );
      const idxB = planetsB.findIndex(
        (p) => p.name.toLowerCase() === a.p2_name.toLowerCase(),
      );
      if (idxA === -1 || idxB === -1) return null;
      const pa = polar(adjustedA[idxA] ?? planetsA[idxA].degree, R_ASPECT);
      const pb = polar(adjustedB[idxB] ?? planetsB[idxB].degree, R_ASPECT);
      return {
        key: `${a.p1_name}-${a.p2_name}-${a.aspect}`,
        x1: pa.x,
        y1: pa.y,
        x2: pb.x,
        y2: pb.y,
        color: ASPECT_COLOR[a.aspect] ?? "rgba(212,178,84,0.4)",
        dash: ASPECT_DASH[a.aspect] ?? "0",
      };
    })
    .filter(Boolean) as {
    key: string;
    x1: number;
    y1: number;
    x2: number;
    y2: number;
    color: string;
    dash: string;
  }[];

  return (
    <div
      style={{
        width: size,
        maxWidth: "100%",
        margin: "0 auto",
        position: "relative",
      }}
    >
      <svg viewBox={`0 0 ${VIEW} ${VIEW}`} width="100%" height="auto">
        {/* Outermost ring */}
        <circle
          cx={CX}
          cy={CY}
          r={R_OUTER}
          fill="none"
          stroke="rgba(212,178,84,0.42)"
          strokeWidth="0.8"
        />
        <circle
          cx={CX}
          cy={CY}
          r={R_ZODIAC}
          fill="none"
          stroke="rgba(212,178,84,0.32)"
          strokeWidth="0.6"
        />

        {/* Zodiac segments */}
        {ZODIAC_ORDER.map((sign, i) => {
          const startDeg = i * 30;
          const start = polar(startDeg, R_OUTER);
          const inner = polar(startDeg, R_ZODIAC);
          const mid = polar(startDeg + 15, (R_OUTER + R_ZODIAC) / 2);
          return (
            <g key={sign}>
              <line
                x1={start.x}
                y1={start.y}
                x2={inner.x}
                y2={inner.y}
                stroke="rgba(212,178,84,0.32)"
                strokeWidth="0.5"
              />
              <image
                href={zodiacIconUrl(sign as ZodiacSign)}
                x={mid.x - 11}
                y={mid.y - 11}
                width={22}
                height={22}
              />
            </g>
          );
        })}

        {/* House cusps */}
        <circle
          cx={CX}
          cy={CY}
          r={R_HOUSE}
          fill="none"
          stroke="rgba(212,178,84,0.18)"
          strokeWidth="0.4"
          strokeDasharray="2 4"
        />
        {housesA?.map((h) => {
          const inner = polar(h.degree, R_HOUSE);
          const outer = polar(h.degree, R_ZODIAC);
          const isAxis = h.number === 1 || h.number === 4 || h.number === 7 || h.number === 10;
          return (
            <line
              key={h.number}
              x1={inner.x}
              y1={inner.y}
              x2={outer.x}
              y2={outer.y}
              stroke={isAxis ? "rgba(232,200,98,0.55)" : "rgba(212,178,84,0.22)"}
              strokeWidth={isAxis ? 0.9 : 0.5}
            />
          );
        })}

        {/* Outer planet ring (partner B) */}
        <circle
          cx={CX}
          cy={CY}
          r={R_PLANET_B}
          fill="none"
          stroke="rgba(212,178,84,0.18)"
          strokeWidth="0.4"
        />
        {planetsB.map((p, i) => {
          const a = adjustedB[i] ?? p.degree;
          const pos = polar(a, R_PLANET_B);
          const tick1 = polar(p.degree, R_PLANET_B + 8);
          const tick2 = polar(p.degree, R_PLANET_B - 4);
          return (
            <g key={`b-${p.name}`}>
              <line
                x1={tick1.x}
                y1={tick1.y}
                x2={tick2.x}
                y2={tick2.y}
                stroke="rgba(232,200,98,0.45)"
                strokeWidth="0.5"
              />
              <text
                x={pos.x}
                y={pos.y}
                fill="rgba(232,200,98,0.95)"
                fontSize="16"
                textAnchor="middle"
                dominantBaseline="central"
                style={{ fontFamily: "serif" }}
              >
                {PLANET_GLYPH[p.name.toLowerCase()] ?? "●"}
              </text>
            </g>
          );
        })}

        {/* Inner planet ring (partner A) */}
        <circle
          cx={CX}
          cy={CY}
          r={R_PLANET_A}
          fill="none"
          stroke="rgba(212,178,84,0.18)"
          strokeWidth="0.4"
        />
        {planetsA.map((p, i) => {
          const a = adjustedA[i] ?? p.degree;
          const pos = polar(a, R_PLANET_A);
          const tick1 = polar(p.degree, R_PLANET_A + 4);
          const tick2 = polar(p.degree, R_PLANET_A - 8);
          return (
            <g key={`a-${p.name}`}>
              <line
                x1={tick1.x}
                y1={tick1.y}
                x2={tick2.x}
                y2={tick2.y}
                stroke="rgba(212,178,84,0.55)"
                strokeWidth="0.5"
              />
              <text
                x={pos.x}
                y={pos.y}
                fill="rgba(212,178,84,0.95)"
                fontSize="14"
                textAnchor="middle"
                dominantBaseline="central"
                style={{ fontFamily: "serif" }}
              >
                {PLANET_GLYPH[p.name.toLowerCase()] ?? "●"}
              </text>
            </g>
          );
        })}

        {/* Aspect lines */}
        <circle
          cx={CX}
          cy={CY}
          r={R_ASPECT}
          fill="none"
          stroke="rgba(212,178,84,0.1)"
          strokeWidth="0.4"
        />
        {aspectLines.map((line) => (
          <line
            key={line.key}
            x1={line.x1}
            y1={line.y1}
            x2={line.x2}
            y2={line.y2}
            stroke={line.color}
            strokeWidth="0.8"
            strokeDasharray={line.dash}
          />
        ))}

        {/* Center mark */}
        <circle cx={CX} cy={CY} r="3" fill="rgba(232,200,98,0.6)" />
      </svg>

      {(initiatorName || partnerName) && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: 6,
            fontSize: 11,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            color: "var(--gold-dim, rgba(212,178,84,0.7))",
          }}
        >
          <span>● Внутри: {initiatorName ?? "вы"}</span>
          <span>○ Снаружи: {partnerName ?? "партнёр"}</span>
        </div>
      )}
    </div>
  );
}
