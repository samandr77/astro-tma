import { useMemo } from 'react';
import type { ChartBodyName, ChartVariant, NatalChartData, PlanetName } from '../types';
import { WHEEL } from '../constants';
import { polar, positionToAbsoluteDegree, zodiacToSvgAngle } from '../utils/geometry';
import { layOutPlanets } from '../utils/planetLayout';
import { AspectLines } from './AspectLines';
import { CenterGlyph } from './CenterGlyph';
import { DegreeLabels } from './DegreeLabels';
import { HouseRing } from './HouseRing';
import { PlanetLayer } from './PlanetLayer';
import { PosterMandala } from './PosterMandala';
import { TickMarks } from './TickMarks';
import { ZodiacRing } from './ZodiacRing';
import { ZodiacSymbolIcon } from './SymbolIcons';
import styles from '../NatalChart.module.css';

interface Props {
  data: NatalChartData;
  variant?: ChartVariant;
  onPlanetClick?: (planet: PlanetName) => void;
  onHouseClick?: (house: number) => void;
}

export function ChartWheel({
  data,
  variant = 'editorial',
  onPlanetClick,
  onHouseClick,
}: Props) {
  const ascendantDegree = useMemo(
    () => positionToAbsoluteDegree(data.ascendant),
    [data.ascendant],
  );

  const isPoster = variant === 'zodiac-poster';
  const isReferenceWheel = variant === 'reference-wheel';
  const isSquareWheel = isPoster || isReferenceWheel;
  const placed = useMemo(
    () => layOutPlanets(data.planets, isReferenceWheel ? 'equal-slots' : 'stacked'),
    [data.planets, isReferenceWheel],
  );
  const referencePlanetSlotCount = Math.max(placed.length, 1);
  const bodyDegrees = useMemo(() => {
    const ascendantAbs = positionToAbsoluteDegree(data.ascendant);
    const midheavenAbs = positionToAbsoluteDegree(data.midheaven);
    const out = {
      ascendant: ascendantAbs,
      descendant: (ascendantAbs + 180) % 360,
      midheaven: midheavenAbs,
      imumCoeli: (midheavenAbs + 180) % 360,
    } as Record<ChartBodyName, number>;

    (Object.keys(data.planets) as PlanetName[]).forEach((name) => {
      const planet = data.planets[name];
      if (!planet || planet.hidden) return;
      out[name] = positionToAbsoluteDegree(planet);
    });

    return out;
  }, [data.ascendant, data.midheaven, data.planets]);
  const referenceAspectDegrees = useMemo(() => {
    const out = { ...bodyDegrees };
    if (!isReferenceWheel) return out;

    placed.forEach((planet) => {
      out[planet.name] = planet.displayAbsDeg;
    });
    return out;
  }, [bodyDegrees, isReferenceWheel, placed]);
  return (
    <g data-part="chart-wheel" transform={`translate(${WHEEL.cx} ${WHEEL.cy})`}>
      {isReferenceWheel && (
        <circle
          r={WHEEL.outerR + 3}
          fill="rgba(24, 14, 58, 0.18)"
          stroke="none"
        />
      )}

      {isSquareWheel && (
        <g data-part="poster-outer-rings">
          <circle
            r={WHEEL.outerR + 66}
            fill="none"
            stroke="var(--natal-accent)"
            strokeWidth={2}
            opacity={0.9}
          />
          <circle
            r={WHEEL.outerR + 52}
            fill="none"
            stroke="var(--natal-accent)"
            strokeWidth={1}
            opacity={isReferenceWheel ? 0.32 : 0.62}
          />
          {!isReferenceWheel && (
            <circle
              r={WHEEL.outerR + 38}
              fill="none"
              stroke="var(--natal-accent)"
              strokeWidth={2}
              strokeDasharray="1 12"
              strokeLinecap="round"
              opacity={0.7}
            />
          )}
          <circle
            r={WHEEL.outerR + 16}
            fill="none"
            stroke="var(--natal-dim)"
            strokeWidth={1}
            opacity={0.62}
          />
        </g>
      )}

      {/* three master circles — the armature of the wheel */}
      <circle r={WHEEL.outerR}  fill="none" stroke="var(--natal-primary)" strokeWidth={1.5} opacity={0.9} />
      <circle r={WHEEL.middleR} fill="none" stroke="var(--natal-primary)" strokeWidth={1.5} opacity={0.9} />
      <circle r={WHEEL.innerR}  fill="none" stroke="var(--natal-primary)" strokeWidth={1.2} opacity={0.8} />

      <TickMarks ascendantDegree={ascendantDegree} variant={variant} />
      <ZodiacRing ascendantDegree={ascendantDegree} variant={variant} />
      <HouseRing
        houses={data.houses}
        ascendantDegree={ascendantDegree}
        variant={variant}
        onHouseClick={onHouseClick}
      />

      {isReferenceWheel && (
        <g data-part="reference-aspect-field">
          <circle
            r={WHEEL.innerR - 12}
            fill="none"
            stroke="var(--natal-accent)"
            strokeWidth={0.7}
            opacity={0.22}
          />
          <circle
            r={WHEEL.innerR - 84}
            fill="none"
            stroke="var(--natal-accent)"
            strokeWidth={0.7}
            opacity={0.22}
          />
          {Array.from({ length: referencePlanetSlotCount }, (_, i) => {
            const svgAng = zodiacToSvgAngle(i * (360 / referencePlanetSlotCount), ascendantDegree);
            const p1 = polar(0, 0, WHEEL.innerR - 84, svgAng);
            const p2 = polar(0, 0, WHEEL.innerR - 12, svgAng);
            return (
              <line
                key={`planet-band-divider-${i}`}
                x1={p1.x}
                y1={p1.y}
                x2={p2.x}
                y2={p2.y}
                stroke="var(--natal-accent)"
                strokeWidth={0.6}
                opacity={0.18}
              />
            );
          })}
        </g>
      )}

      <AspectLines
        aspects={data.aspects}
        bodyDegrees={isReferenceWheel ? referenceAspectDegrees : bodyDegrees}
        ascendantDegree={ascendantDegree}
        variant={variant}
      />

      <PlanetLayer
        placed={placed}
        ascendantDegree={ascendantDegree}
        variant={variant}
        onPlanetClick={onPlanetClick}
      />

      {!isPoster && !isReferenceWheel && (
        <DegreeLabels placed={placed} ascendantDegree={ascendantDegree} />
      )}

      {isPoster ? (
        <PosterMandala />
      ) : isReferenceWheel ? (
        <g data-part="reference-center">
          <circle
            r={44}
            fill="rgba(5, 7, 24, 0.92)"
            stroke="var(--natal-accent)"
            strokeWidth={1.4}
            opacity={0.96}
          />
          <circle
            r={38}
            fill="none"
            stroke="var(--natal-accent)"
            strokeWidth={0.6}
            opacity={0.72}
          />
          <circle
            r={14}
            fill="rgba(5, 7, 24, 0.72)"
            stroke="var(--natal-accent)"
            strokeWidth={0.65}
            opacity={0.9}
          />
          <g transform="translate(-34 -34)" className={styles.referenceCenterSymbol}>
            <ZodiacSymbolIcon sign={data.ascendant.sign} size={68} strokeWidth={1.9} />
          </g>
        </g>
      ) : (
        <CenterGlyph />
      )}
    </g>
  );
}
