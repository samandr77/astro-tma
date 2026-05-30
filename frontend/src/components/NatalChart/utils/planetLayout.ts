import type { PlanetName, PlanetPosition } from '../types';
import { PLANET_DRAW_ORDER, WHEEL, ZODIAC_ORDER } from '../constants';
import { positionToAbsoluteDegree } from './geometry';

export interface PlacedPlanet {
  name: PlanetName;
  position: PlanetPosition;
  absDeg: number;
  /** Visual degree after collision spreading. Keeps dense clusters legible. */
  displayAbsDeg: number;
  /** Radius at which the glyph is drawn (after collision offset). */
  radius: number;
}

const COLLISION_GAP = 38;   // degrees within which we offset radially
const CLUSTER_SPACING = 22;
const CLUSTER_RADIAL_OFFSETS = [0, -20, 20, -42, 42, -64, 64, -86];
const SIGN_SLOT_PADDING = 0;

type LayoutMode = 'stacked' | 'zodiac-band' | 'equal-slots';

/** Sort planets by absolute degree, then push stacked radii inward when
 *  successive planets fall within `COLLISION_GAP`. */
export function layOutPlanets(
  planets: Record<PlanetName, PlanetPosition>,
  mode: LayoutMode = 'stacked',
): PlacedPlanet[] {
  const placed: PlacedPlanet[] = PLANET_DRAW_ORDER.flatMap((name) => {
    const position = planets[name];
    if (!position || position.hidden) return [];
    return [{
      name,
      position,
      absDeg: positionToAbsoluteDegree(position),
      displayAbsDeg: positionToAbsoluteDegree(position),
      radius: WHEEL.planetR,
    }];
  });

  placed.sort((a, b) => a.absDeg - b.absDeg);

  if (mode === 'equal-slots') {
    const ordered = PLANET_DRAW_ORDER.flatMap((name) => {
      const planet = placed.find((item) => item.name === name);
      return planet ? [planet] : [];
    });
    const step = 360 / ordered.length;
    ordered.forEach((planet, slot) => {
      planet.displayAbsDeg = slot * step + step / 2;
      planet.radius = WHEEL.planetR;
    });
    return placed;
  }

  if (mode === 'zodiac-band') {
    ZODIAC_ORDER.forEach((sign, signIndex) => {
      const inSign = placed
        .filter((planet) => planet.position.sign === sign)
        .sort((a, b) => a.absDeg - b.absDeg);

      if (!inSign.length) return;

      inSign.forEach((planet, index) => {
        const step = (30 - SIGN_SLOT_PADDING * 2) / (inSign.length + 1);
        planet.displayAbsDeg = signIndex * 30 + SIGN_SLOT_PADDING + step * (index + 1);
        planet.radius = WHEEL.planetR;
      });
    });

    return placed;
  }

  if (placed.length <= 1) return placed;

  const largestGap = placed.reduce(
    (best, planet, index) => {
      const next = placed[(index + 1) % placed.length];
      const gap = (next.absDeg - planet.absDeg + 360) % 360;
      return gap > best.gap ? { index, gap } : best;
    },
    { index: 0, gap: -1 },
  );

  const ordered = [
    ...placed.slice(largestGap.index + 1),
    ...placed.slice(0, largestGap.index + 1),
  ];

  let clusterStart = 0;
  for (let i = 1; i <= ordered.length; i++) {
    const previous = ordered[i - 1];
    const current = ordered[i];
    const isClustered =
      current && (current.absDeg - previous.absDeg + 360) % 360 < COLLISION_GAP;

    if (isClustered) continue;

    const clusterSize = i - clusterStart;
    const centerDeg =
      ordered
        .slice(clusterStart, i)
        .reduce((sum, planet) => {
          const normalized =
            planet.absDeg < ordered[clusterStart].absDeg
              ? planet.absDeg + 360
              : planet.absDeg;
          return sum + normalized;
        }, 0) / clusterSize;

    for (let j = clusterStart; j < i; j++) {
      const localIndex = j - clusterStart;
      const offsetIndex = Math.min(localIndex, CLUSTER_RADIAL_OFFSETS.length - 1);
      const angularOffset =
        clusterSize > 1
          ? (localIndex - (clusterSize - 1) / 2) * CLUSTER_SPACING
          : 0;
      ordered[j].displayAbsDeg = (centerDeg + angularOffset + 360) % 360;
      ordered[j].radius = WHEEL.planetR + CLUSTER_RADIAL_OFFSETS[offsetIndex];
    }
    clusterStart = i;
  }

  return placed;
}
