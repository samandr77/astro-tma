import type { PlanetName, ZodiacSign } from '../types';

const ZODIAC_PATHS: Record<ZodiacSign, string> = {
  aries:
    'M16 30 V15 M16 15 C9 8 4 12 6 18 C7 21 11 22 14 19 M16 15 C23 8 28 12 26 18 C25 21 21 22 18 19',
  taurus:
    'M16 24 m-6 0 a6 6 0 1 0 12 0 a6 6 0 1 0 -12 0 M10 18 C7 12 11 6 16 9 C21 6 25 12 22 18',
  gemini:
    'M11 7 V25 M21 7 V25 M8 7 H14 M18 7 H24 M8 25 H14 M18 25 H24',
  cancer:
    'M11 12 m-3 0 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0 M8 12 C8 6 18 5 24 9 M21 22 m-3 0 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0 M24 22 C24 28 14 29 8 25',
  leo:
    'M12 14 m-4 0 a4 4 0 1 0 8 0 a4 4 0 1 0 -8 0 M16 14 C17 22 23 24 26 20 C27 16 23 14 21 17 C20 19 22 21 24 21',
  virgo:
    'M7 26 V12 C7 8 13 8 13 12 V26 M13 12 C13 8 19 8 19 12 V26 M19 12 C19 8 25 8 25 14 C25 18 21 22 17 20 C20 23 24 25 26 28',
  libra:
    'M5 24 H27 M7 20 C9 13 23 13 25 20 M13 17 H19',
  scorpio:
    'M5 26 V12 C5 8 11 8 11 12 V26 M11 12 C11 8 17 8 17 12 V26 M17 12 C17 8 25 8 25 18 L25 27 M21 23 L25 27 L29 23',
  sagittarius:
    'M6 26 L26 6 M17 6 H26 V15 M10 14 L18 22',
  capricorn:
    'M5 9 L11 22 L17 9 L21 22 C23 27 29 26 28 21 C27 18 22 18 22 22',
  aquarius:
    'M4 13 Q8 8 12 13 T20 13 T28 13 M4 22 Q8 17 12 22 T20 22 T28 22',
  pisces:
    'M9 6 Q3 16 9 26 M23 6 Q29 16 23 26 M5 16 H27',
};

const PLANET_PATHS: Record<PlanetName, { strokes: string[]; dots?: [number, number, number][] }> = {
  sun: {
    strokes: ['M16 16 m-8 0 a8 8 0 1 0 16 0 a8 8 0 1 0 -16 0'],
    dots: [[16, 16, 1.6]],
  },
  moon: {
    strokes: ['M22 6 C14 8 10 14 11 20 C12 24 16 27 22 26 C16 22 14 14 22 6'],
  },
  mercury: {
    strokes: [
      'M16 14 m-5 0 a5 5 0 1 0 10 0 a5 5 0 1 0 -10 0',
      'M16 19 V28 M12 24 H20',
      'M10 6 C12 10 20 10 22 6',
    ],
  },
  venus: {
    strokes: [
      'M16 12 m-5 0 a5 5 0 1 0 10 0 a5 5 0 1 0 -10 0',
      'M16 17 V28 M12 24 H20',
    ],
  },
  mars: {
    strokes: [
      'M14 20 m-5 0 a5 5 0 1 0 10 0 a5 5 0 1 0 -10 0',
      'M18 16 L26 8 M21 8 H26 V13',
    ],
  },
  jupiter: {
    strokes: ['M8 10 C8 6 14 6 14 12 V24 H22 M14 24 C14 27 19 27 19 24'],
  },
  saturn: {
    strokes: ['M10 6 V8 H14 V20 C14 26 22 26 22 22 C22 18 18 18 16 21'],
  },
  uranus: {
    strokes: [
      'M8 6 V14 M24 6 V14 M8 10 H24 M16 10 V22',
      'M16 26 m-3 0 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0',
    ],
  },
  neptune: {
    strokes: ['M8 8 V14 C8 22 24 22 24 14 V8 M16 8 V26 M12 22 H20'],
  },
  pluto: {
    strokes: [
      'M10 12 C10 6 22 6 22 12',
      'M16 16 m-3 0 a3 3 0 1 0 6 0 a3 3 0 1 0 -6 0',
      'M16 19 V28 M12 24 H20',
    ],
  },
  northNode: {
    strokes: ['M8 24 V14 C8 6 24 6 24 14 V24'],
    dots: [[8, 26, 1.6], [24, 26, 1.6]],
  },
  chiron: {
    strokes: ['M16 5 V27 M10 10 H22 M16 16 L23 23 M16 16 L9 23'],
  },
};

interface IconProps {
  sign?: ZodiacSign;
  planet?: PlanetName;
  size: number;
  strokeWidth?: number;
}

export function ZodiacSymbolIcon({ sign, size, strokeWidth = 1.7 }: IconProps) {
  if (!sign) return null;
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className="natal-symbol-icon">
      <path
        d={ZODIAC_PATHS[sign]}
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function PlanetSymbolIcon({ planet, size, strokeWidth = 1.8 }: IconProps) {
  if (!planet) return null;
  const def = PLANET_PATHS[planet];
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className="natal-symbol-icon">
      {def.strokes.map((d, i) => (
        <path
          key={i}
          d={d}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
      {def.dots?.map(([cx, cy, r], i) => (
        <circle key={i} cx={cx} cy={cy} r={r} fill="currentColor" />
      ))}
    </svg>
  );
}
