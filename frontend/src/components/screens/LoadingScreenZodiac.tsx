import styles from './LoadingScreenZodiac.module.css';
import { zodiacIconUrl } from '@/components/ui/ZodiacIcon';
import type { ZodiacSign } from '@/components/NatalChart/types';

const CX = 250;
const CY = 250;

// 12 zodiac signs in clockwise order from Aries
const ZODIAC_ORDER: ZodiacSign[] = [
  'aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo',
  'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces',
];

// Ring midline radii (matched to the existing wheel-grid.svg)
const R_LARGE  = (218 + 165) / 2; // ≈ 191.5
const R_MID    = (160 + 118) / 2; // ≈ 139
const R_SMALL  = (113 + 82) / 2;  // ≈ 97.5

const ICON_SIZE_LARGE = 38;
const ICON_SIZE_MID   = 26;
const ICON_SIZE_SMALL = 18;

function pt(r: number, angleDeg: number) {
  const rad = (angleDeg - 90) * (Math.PI / 180);
  return {
    x: +(CX + r * Math.cos(rad)).toFixed(2),
    y: +(CY + r * Math.sin(rad)).toFixed(2),
  };
}

function GlyphRing({
  radius,
  iconSize,
  className,
}: {
  radius: number;
  iconSize: number;
  className: string;
}) {
  return (
    <g className={className} style={{ transformOrigin: '250px 250px' }}>
      {ZODIAC_ORDER.map((sign, i) => {
        const { x, y } = pt(radius, i * 30 + 15);
        return (
          <image
            key={sign}
            href={zodiacIconUrl(sign)}
            x={x - iconSize / 2}
            y={y - iconSize / 2}
            width={iconSize}
            height={iconSize}
          />
        );
      })}
    </g>
  );
}

export function LoadingScreenZodiac() {
  return (
    <div className={styles.screen}>
      {/* Фон со звёздами + туманности — растягивается на весь экран */}
      <img src="/zodiac/01-background-stars.svg" alt="" className={styles.bg} />

      {/* Стек колец — все слои одного размера, наложены друг на друга */}
      <div className={styles.wheel}>
        <img src="/zodiac/02-wheel-grid.svg"  alt="" className={styles.layer} />
        <img src="/zodiac/03-wheel-names.svg" alt="" className={`${styles.layer} ${styles.spinCw70}`} />

        {/* Inline-генерируемые кольца знаков — используют новые SVG-глифы */}
        <svg
          viewBox="0 0 500 500"
          className={styles.layer}
          aria-hidden="true"
        >
          <GlyphRing radius={R_LARGE} iconSize={ICON_SIZE_LARGE} className={styles.spinCw70} />
          <GlyphRing radius={R_MID}   iconSize={ICON_SIZE_MID}   className={styles.spinCcw90} />
          <GlyphRing radius={R_SMALL} iconSize={ICON_SIZE_SMALL} className={styles.spinCw150} />
        </svg>

        <img src="/zodiac/07-center-sun.svg" alt="" className={`${styles.layer} ${styles.pulseSun}`} />
      </div>

      {/* Подпись */}
      <div className={styles.footer}>
        <h1 className={styles.title}>ASTRO</h1>
        <div className={styles.dots} aria-hidden="true">
          <span /><span /><span />
        </div>
      </div>
    </div>
  );
}
