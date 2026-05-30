import { useMemo } from 'react';
import type { Aspect, ChartBodyName, ChartVariant, PlanetName } from '../types';
import { WHEEL } from '../constants';
import { polar, zodiacToSvgAngle } from '../utils/geometry';
import { getAspectStyle } from '../utils/aspects';

interface Props {
  aspects: Aspect[];
  bodyDegrees: Record<ChartBodyName, number>;
  ascendantDegree: number;
  variant?: ChartVariant;
}

/** Keep aspect lines inside the planet glyph ring so they don't visually cross labels. */
const EDGE_INSET = 4;
const REFERENCE_ASPECT_R = 120;
const REFERENCE_MAX_ASPECTS = 6;
const PLANET_NAMES: ReadonlySet<string> = new Set<PlanetName>([
  'sun',
  'moon',
  'mercury',
  'venus',
  'mars',
  'jupiter',
  'saturn',
  'uranus',
  'neptune',
  'pluto',
  'northNode',
  'chiron',
]);

export function AspectLines({
  aspects,
  bodyDegrees,
  ascendantDegree,
  variant = 'editorial',
}: Props) {
  const isReferenceWheel = variant === 'reference-wheel';
  const angles = useMemo(() => {
    const out = {} as Record<ChartBodyName, number>;
    (Object.keys(bodyDegrees) as ChartBodyName[]).forEach((name) => {
      out[name] = zodiacToSvgAngle(bodyDegrees[name], ascendantDegree);
    });
    return out;
  }, [bodyDegrees, ascendantDegree]);

  const displayAspects = useMemo(
    () => {
      if (!isReferenceWheel) return aspects;

      return [...aspects]
        .filter((aspect) => PLANET_NAMES.has(aspect.planet1) && PLANET_NAMES.has(aspect.planet2))
        .sort((a, b) => a.orb - b.orb)
        .slice(0, REFERENCE_MAX_ASPECTS);
    },
    [aspects, isReferenceWheel],
  );
  const r = isReferenceWheel ? REFERENCE_ASPECT_R : WHEEL.innerR - EDGE_INSET;

  return (
    <g data-part="aspect-lines">
      {displayAspects.map((asp, i) => {
        const a1 = angles[asp.planet1];
        const a2 = angles[asp.planet2];
        // Skip if we somehow don't have a position for either planet.
        if (a1 === undefined || a2 === undefined) return null;

        const p1 = polar(0, 0, r, a1);
        const p2 = polar(0, 0, r, a2);
        const s = getAspectStyle(asp.type);
        const referenceOpacity = Math.max(0.22, Math.min(0.52, 0.58 - asp.orb * 0.055));

        return isReferenceWheel ? (
          <g key={`${asp.planet1}-${asp.planet2}-${asp.type}-${i}`}>
            <line
              x1={p1.x}
              y1={p1.y}
              x2={p2.x}
              y2={p2.y}
              stroke="var(--natal-accent)"
              strokeWidth={2.4}
              strokeLinecap="round"
              opacity={0.05}
            />
            <line
              x1={p1.x}
              y1={p1.y}
              x2={p2.x}
              y2={p2.y}
              stroke="var(--natal-accent)"
              strokeWidth={0.9}
              strokeLinecap="round"
              opacity={referenceOpacity}
              vectorEffect="non-scaling-stroke"
            />
            <circle cx={p1.x} cy={p1.y} r={1.9} fill="var(--natal-accent)" opacity={referenceOpacity + 0.14} />
            <circle cx={p2.x} cy={p2.y} r={1.9} fill="var(--natal-accent)" opacity={referenceOpacity + 0.14} />
          </g>
        ) : (
          <line
            key={`${asp.planet1}-${asp.planet2}-${asp.type}-${i}`}
            x1={p1.x}
            y1={p1.y}
            x2={p2.x}
            y2={p2.y}
            stroke={s.stroke}
            strokeWidth={1}
            strokeDasharray={s.dasharray}
            opacity={s.opacity}
          />
        );
      })}
    </g>
  );
}
