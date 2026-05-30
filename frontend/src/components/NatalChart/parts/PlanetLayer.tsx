import clsx from 'clsx';
import type { PlacedPlanet } from '../utils/planetLayout';
import type { ChartVariant, PlanetName } from '../types';
import { PLANET_GLYPH, PLANET_LABEL, RETROGRADE_MARK, WHEEL, ZODIAC_LABEL } from '../constants';
import { polar, zodiacToSvgAngle } from '../utils/geometry';
import { formatDegreeMinute } from '../utils/formatting';
import styles from '../NatalChart.module.css';
import { PlanetSymbolIcon } from './SymbolIcons';

interface Props {
  placed: PlacedPlanet[];
  ascendantDegree: number;
  variant?: ChartVariant;
  onPlanetClick?: (planet: PlanetName) => void;
}

const GLYPH_FONT_SIZE = 27;
const REFERENCE_PLANET_BAND_INNER_R = WHEEL.innerR - 84;
const REFERENCE_PLANET_BAND_OUTER_R = WHEEL.innerR - 12;
const REFERENCE_PLANET_BASE_R =
  (REFERENCE_PLANET_BAND_INNER_R + REFERENCE_PLANET_BAND_OUTER_R) / 2;
const REFERENCE_PLANET_ICON_SIZE = 30;

export function PlanetLayer({
  placed,
  ascendantDegree,
  variant = 'editorial',
  onPlanetClick,
}: Props) {
  const isReferenceWheel = variant === 'reference-wheel';

  return (
    <g data-part="planet-layer">
      {placed.map(({ name, position, absDeg, displayAbsDeg, radius }) => {
        const visualDegree = isReferenceWheel ? displayAbsDeg : absDeg;
        const svgAng = zodiacToSvgAngle(visualDegree, ascendantDegree);
        const referenceRadius = REFERENCE_PLANET_BASE_R + (radius - WHEEL.planetR) * 0.12;
        const pos = polar(0, 0, isReferenceWheel ? referenceRadius : radius, svgAng);

        const interactive = Boolean(onPlanetClick);
        const handleClick = onPlanetClick ? () => onPlanetClick(name) : undefined;
        const handleKey = onPlanetClick
          ? (e: React.KeyboardEvent) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onPlanetClick(name);
              }
            }
          : undefined;

        const srDescription =
          `${PLANET_LABEL[name]} ${formatDegreeMinute(position)} в знаке ${ZODIAC_LABEL[position.sign]}` +
          (position.retrograde ? ' (ретроградная)' : '') +
          `, дом ${position.house}`;

        return (
          <g
            key={name}
            data-planet={name}
            className={clsx(interactive && styles.interactive)}
            tabIndex={interactive ? 0 : undefined}
            onClick={handleClick}
            onKeyDown={handleKey}
            role={interactive ? 'button' : undefined}
            aria-label={interactive ? srDescription : undefined}
          >
            {isReferenceWheel ? (
              <g transform={`translate(${pos.x} ${pos.y})`}>
                <g
                  transform={`translate(${-REFERENCE_PLANET_ICON_SIZE / 2} ${-REFERENCE_PLANET_ICON_SIZE / 2})`}
                  className={styles.referencePlanetSymbol}
                >
                  <PlanetSymbolIcon
                    planet={name}
                    size={REFERENCE_PLANET_ICON_SIZE}
                    strokeWidth={2}
                  />
                </g>
              </g>
            ) : (
              <>
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={15}
                  fill="rgba(5, 7, 24, 0.84)"
                  stroke="var(--natal-accent)"
                  strokeWidth={0.6}
                  opacity={0.62}
                />
                <text
                  x={pos.x}
                  y={pos.y}
                  dy="0.05em"
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={GLYPH_FONT_SIZE}
                  fill="var(--natal-primary)"
                  className={styles.glyphText}
                >
                  {PLANET_GLYPH[name]}
                </text>
                {position.retrograde && (
                  <text
                    x={pos.x + 13}
                    y={pos.y - 12}
                    textAnchor="middle"
                    dominantBaseline="central"
                    fontSize={10}
                    fill="var(--natal-dim)"
                    className={styles.bodyText}
                  >
                    {RETROGRADE_MARK}
                  </text>
                )}
              </>
            )}
          </g>
        );
      })}
    </g>
  );
}
