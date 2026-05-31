/**
 * Synastry bi-wheel — two natal charts overlaid in concentric rings.
 *
 * Outer ring  — zodiac signs with SVG glyphs (same set as the natal chart)
 * Tick marks  — every 5°, taller every 30° (sign boundaries) — matches natal
 * House ring  — partner A's house cusps as faint radial dividers
 * B planets   — partner B planets on the outer planet ring
 * A planets   — partner A planets on the inner planet ring (yours)
 * Aspect lines — chords between the two planet sets in the center
 *
 * Visual language deliberately mirrors NatalChart so a user already
 * familiar with the natal screen recognises this as "two of those, layered."
 *
 * Pure presentational: takes pre-computed planet/aspect data, renders SVG.
 */
import { PlanetSymbolIcon, ZodiacSymbolIcon } from "@/components/NatalChart/parts/SymbolIcons";
import type { PlanetName, ZodiacSign } from "@/components/NatalChart/types";
import type {
  SynastryAspectOut,
  SynastryHouseInfo,
  SynastryPlanetInfo,
} from "@/types";

const ZODIAC_ORDER: ZodiacSign[] = [
  "aries", "taurus", "gemini", "cancer",
  "leo", "virgo", "libra", "scorpio",
  "sagittarius", "capricorn", "aquarius", "pisces",
];

// Map backend planet names to NatalChart PlanetName glyphs.
const PLANET_NAME_MAP: Record<string, PlanetName> = {
  sun: "sun", moon: "moon", mercury: "mercury", venus: "venus", mars: "mars",
  jupiter: "jupiter", saturn: "saturn", uranus: "uranus", neptune: "neptune",
  pluto: "pluto", chiron: "chiron",
  true_node: "northNode", mean_node: "northNode", north_node: "northNode",
};

const ASPECT_COLOR: Record<string, string> = {
  conjunction: "rgba(232, 200, 98, 0.92)",
  trine:       "rgba(139, 200, 155, 0.80)",
  sextile:     "rgba(126, 200, 227, 0.78)",
  square:      "rgba(232, 139, 139, 0.78)",
  opposition:  "rgba(197, 139, 232, 0.78)",
};

const ASPECT_DASH: Record<string, string> = {
  conjunction: "0",
  trine:       "0",
  sextile:     "0",
  square:      "4 4",
  opposition:  "6 4",
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

// ── Geometry ──────────────────────────────────────────────────────────────
const VIEW = 640;
const CX = VIEW / 2;
const CY = VIEW / 2;

const R_TICK_OUT  = 304;        // outer end of major ticks
const R_TICK_MAJ  = 296;        // outer end of minor ticks
const R_ZODIAC_OUT = 288;       // outer zodiac ring
const R_ZODIAC_IN  = 248;       // inner zodiac ring (glyphs sit centered between)
const R_HOUSE      = 232;       // house cusps end
const R_PLANET_B   = 212;       // partner B planets (outer)
const R_PLANET_B_TICK_OUT = 224;
const R_PLANET_B_TICK_IN  = 200;
const R_RING_MID   = 178;       // mid divider ring between A and B
const R_PLANET_A   = 156;       // partner A planets (inner)
const R_PLANET_A_TICK_OUT = 168;
const R_PLANET_A_TICK_IN  = 144;
const R_ASPECT     = 128;       // aspect lines bounded inside this radius

const GLYPH_SIZE_B = 22;
const GLYPH_SIZE_A = 20;
const ZODIAC_GLYPH = 24;

// Two visually distinct colors for the two charts so it's obvious at a
// glance which planet belongs to whom. Gold (you) vs cool blue (partner)
// reads cleanly on the dark backdrop.
const COLOR_INNER = "#e8c862";   // you  — gold
const COLOR_OUTER = "#7ec6f0";   // partner — cool blue

/** Astrological convention: 0° Aries at the left, going CCW.
 *  SVG y goes down, so we flip the angle. */
function polar(deg: number, r: number): { x: number; y: number } {
  const rad = ((180 - deg) * Math.PI) / 180;
  return { x: CX + r * Math.cos(rad), y: CY + r * Math.sin(rad) };
}

/** Greedy anti-overlap: pull adjacent planets along the ring so glyphs
 *  don't stack on top of each other. Returns adjusted display degree per
 *  input planet. minGap is the minimum angular distance between centers. */
function spreadGlyphs(planets: SynastryPlanetInfo[], minGap = 9): number[] {
  if (!planets.length) return [];
  const sorted = planets
    .map((p, i) => ({ idx: i, deg: p.degree }))
    .sort((a, b) => a.deg - b.deg);

  const adjusted = sorted.map((s) => ({ ...s }));
  for (let i = 1; i < adjusted.length; i++) {
    const prev = adjusted[i - 1];
    if (adjusted[i].deg - prev.deg < minGap) {
      adjusted[i].deg = prev.deg + minGap;
    }
  }
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

  // Single uppercase letter shown beside each planet so the reader knows
  // whose it is. Defaults to "Я" / "П" if no name was provided.
  const initialA = (initiatorName?.trim().charAt(0) || "Я").toUpperCase();
  const initialB = (partnerName?.trim().charAt(0) || "П").toUpperCase();

  // Aspect chords — from A's real degree to B's real degree (lines stay
  // honest to actual positions, glyph nudging is purely visual).
  const aspectLines = aspects
    .map((a) => {
      const idxA = planetsA.findIndex(
        (p) => p.name.toLowerCase() === a.p1_name.toLowerCase(),
      );
      const idxB = planetsB.findIndex(
        (p) => p.name.toLowerCase() === a.p2_name.toLowerCase(),
      );
      if (idxA === -1 || idxB === -1) return null;
      const pa = polar(planetsA[idxA].degree, R_ASPECT);
      const pb = polar(planetsB[idxB].degree, R_ASPECT);
      return {
        key: `${a.p1_name}-${a.p2_name}-${a.aspect}`,
        x1: pa.x, y1: pa.y, x2: pb.x, y2: pb.y,
        color: ASPECT_COLOR[a.aspect] ?? "rgba(212,178,84,0.45)",
        dash: ASPECT_DASH[a.aspect] ?? "0",
      };
    })
    .filter(Boolean) as {
    key: string; x1: number; y1: number; x2: number; y2: number;
    color: string; dash: string;
  }[];

  return (
    <div
      className="synastry-biwheel"
      style={{ width: size, maxWidth: "100%", margin: "0 auto", position: "relative" }}
    >
      <svg viewBox={`0 0 ${VIEW} ${VIEW}`} width="100%" height="auto">
        {/* ── Backdrop / armature rings ──────────────────────────── */}
        <circle cx={CX} cy={CY} r={R_ZODIAC_OUT}
          fill="none" stroke="var(--natal-primary, rgba(212,178,84,0.7))"
          strokeWidth="1.4" opacity="0.85" />
        <circle cx={CX} cy={CY} r={R_ZODIAC_IN}
          fill="none" stroke="var(--natal-primary, rgba(212,178,84,0.7))"
          strokeWidth="1.0" opacity="0.7" />
        <circle cx={CX} cy={CY} r={R_RING_MID}
          fill="none" stroke="var(--natal-dim, rgba(212,178,84,0.32))"
          strokeWidth="0.7" opacity="0.55" />
        <circle cx={CX} cy={CY} r={R_ASPECT}
          fill="none" stroke="var(--natal-dim, rgba(212,178,84,0.32))"
          strokeWidth="0.6" opacity="0.4" />

        {/* ── Tick marks: every 5°, longer on sign boundaries ────── */}
        {Array.from({ length: 72 }, (_, i) => {
          const d = i * 5;
          const isMajor = d % 30 === 0;
          const outer = isMajor ? R_TICK_OUT : R_TICK_MAJ;
          const a = polar(d, R_ZODIAC_OUT);
          const b = polar(d, outer);
          return (
            <line key={d}
              x1={a.x} y1={a.y} x2={b.x} y2={b.y}
              stroke="var(--natal-dim, rgba(212,178,84,0.32))"
              strokeWidth={isMajor ? 1.0 : 0.6} />
          );
        })}

        {/* ── Zodiac segments + glyphs ──────────────────────────── */}
        {ZODIAC_ORDER.map((sign, i) => {
          const startDeg = i * 30;
          const start = polar(startDeg, R_ZODIAC_OUT);
          const inner = polar(startDeg, R_ZODIAC_IN);
          const midRad = (R_ZODIAC_OUT + R_ZODIAC_IN) / 2;
          const mid = polar(startDeg + 15, midRad);
          return (
            <g key={sign}>
              <line x1={start.x} y1={start.y} x2={inner.x} y2={inner.y}
                stroke="var(--natal-primary, rgba(212,178,84,0.55))"
                strokeWidth="0.8" opacity="0.7" />
              <g transform={`translate(${mid.x - ZODIAC_GLYPH / 2}, ${mid.y - ZODIAC_GLYPH / 2})`}
                 style={{ color: "var(--natal-accent, #e8c862)" }}>
                <ZodiacSymbolIcon sign={sign} size={ZODIAC_GLYPH} strokeWidth={1.6} />
              </g>
            </g>
          );
        })}

        {/* ── House cusps (initiator A) ──────────────────────────── */}
        <circle cx={CX} cy={CY} r={R_HOUSE}
          fill="none" stroke="var(--natal-dim, rgba(212,178,84,0.22))"
          strokeWidth="0.5" strokeDasharray="2 5" opacity="0.6" />
        {housesA?.map((h) => {
          const isAxis = h.number === 1 || h.number === 4 || h.number === 7 || h.number === 10;
          const inner = polar(h.degree, R_HOUSE);
          const outer = polar(h.degree, R_ZODIAC_IN);
          return (
            <line key={h.number}
              x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y}
              stroke={isAxis
                ? "var(--natal-accent, rgba(232,200,98,0.65))"
                : "var(--natal-dim, rgba(212,178,84,0.25))"}
              strokeWidth={isAxis ? 1.0 : 0.5}
              opacity={isAxis ? 0.85 : 0.6} />
          );
        })}

        {/* ── Outer planet ring (partner B — BLUE) ──────────────── */}
        {/* faint background tint of the ring, blue */}
        <circle cx={CX} cy={CY} r={R_PLANET_B}
          fill="none" stroke={COLOR_OUTER} strokeOpacity="0.35" strokeWidth="0.9" />
        {planetsB.map((p, i) => {
          const a = adjustedB[i] ?? p.degree;
          const pos = polar(a, R_PLANET_B);
          // Initial pushed outward, away from center, along the same ray.
          const initialPos = polar(a, R_PLANET_B + 14);
          const tick1 = polar(p.degree, R_PLANET_B_TICK_OUT);
          const tick2 = polar(p.degree, R_PLANET_B_TICK_IN);
          const planetKey = PLANET_NAME_MAP[p.name.toLowerCase()];
          return (
            <g key={`b-${p.name}-${i}`}>
              <line x1={tick1.x} y1={tick1.y} x2={tick2.x} y2={tick2.y}
                stroke={COLOR_OUTER} strokeOpacity="0.75" strokeWidth="0.7" />
              {planetKey ? (
                <g transform={`translate(${pos.x - GLYPH_SIZE_B / 2}, ${pos.y - GLYPH_SIZE_B / 2})`}
                   style={{ color: COLOR_OUTER }}>
                  <PlanetSymbolIcon planet={planetKey} size={GLYPH_SIZE_B} strokeWidth={1.9} />
                </g>
              ) : (
                <circle cx={pos.x} cy={pos.y} r="4" fill={COLOR_OUTER} />
              )}
              {/* Initial letter so it's obvious whose planet this is */}
              <text x={initialPos.x} y={initialPos.y}
                fill={COLOR_OUTER} fontSize="9" fontWeight="700"
                textAnchor="middle" dominantBaseline="central"
                style={{ letterSpacing: "0.04em" }}>
                {initialB}
              </text>
            </g>
          );
        })}

        {/* ── Inner planet ring (initiator A — GOLD) ────────────── */}
        <circle cx={CX} cy={CY} r={R_PLANET_A}
          fill="none" stroke={COLOR_INNER} strokeOpacity="0.35" strokeWidth="0.9" />
        {planetsA.map((p, i) => {
          const a = adjustedA[i] ?? p.degree;
          const pos = polar(a, R_PLANET_A);
          // Initial pushed inward toward center for A so it doesn't
          // collide with the outer ring's tick marks.
          const initialPos = polar(a, R_PLANET_A - 14);
          const tick1 = polar(p.degree, R_PLANET_A_TICK_OUT);
          const tick2 = polar(p.degree, R_PLANET_A_TICK_IN);
          const planetKey = PLANET_NAME_MAP[p.name.toLowerCase()];
          return (
            <g key={`a-${p.name}-${i}`}>
              <line x1={tick1.x} y1={tick1.y} x2={tick2.x} y2={tick2.y}
                stroke={COLOR_INNER} strokeOpacity="0.75" strokeWidth="0.7" />
              {planetKey ? (
                <g transform={`translate(${pos.x - GLYPH_SIZE_A / 2}, ${pos.y - GLYPH_SIZE_A / 2})`}
                   style={{ color: COLOR_INNER }}>
                  <PlanetSymbolIcon planet={planetKey} size={GLYPH_SIZE_A} strokeWidth={1.9} />
                </g>
              ) : (
                <circle cx={pos.x} cy={pos.y} r="3.5" fill={COLOR_INNER} />
              )}
              <text x={initialPos.x} y={initialPos.y}
                fill={COLOR_INNER} fontSize="9" fontWeight="700"
                textAnchor="middle" dominantBaseline="central"
                style={{ letterSpacing: "0.04em" }}>
                {initialA}
              </text>
            </g>
          );
        })}

        {/* ── Aspect chords ─────────────────────────────────────── */}
        {aspectLines.map((line) => (
          <line key={line.key}
            x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2}
            stroke={line.color} strokeWidth="0.95"
            strokeDasharray={line.dash} opacity="0.85" />
        ))}

        {/* Center mark */}
        <circle cx={CX} cy={CY} r="4"
          fill="rgba(232,200,98,0.6)" stroke="var(--natal-accent, #e8c862)" strokeWidth="0.6" />
      </svg>

      <div className="synastry-biwheel__legend">
        <span className="synastry-biwheel__legend-item synastry-biwheel__legend-item--inner">
          <span className="synastry-biwheel__legend-badge"
                style={{ background: COLOR_INNER, color: "#0a0906" }}>
            {initialA}
          </span>
          <span>{initiatorName ?? "Вы"}</span>
          <span className="synastry-biwheel__legend-where">— внутреннее кольцо</span>
        </span>
        <span className="synastry-biwheel__legend-item synastry-biwheel__legend-item--outer">
          <span className="synastry-biwheel__legend-badge"
                style={{ background: COLOR_OUTER, color: "#0a0906" }}>
            {initialB}
          </span>
          <span>{partnerName ?? "Партнёр"}</span>
          <span className="synastry-biwheel__legend-where">— внешнее кольцо</span>
        </span>
      </div>
    </div>
  );
}
