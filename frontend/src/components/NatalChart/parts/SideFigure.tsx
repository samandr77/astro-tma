import type { ZodiacSign } from '../types';
import { ZODIAC_LABEL } from '../constants';
import { zodiacIconUrl } from '@/components/ui/ZodiacIcon';
import styles from '../NatalChart.module.css';

interface Props {
  sign: ZodiacSign;
  side: 'left' | 'right';
}

/** Small 4-point accent star used as ornamental flourish. */
function AccentStar({ cx, cy, size }: { cx: number; cy: number; size: number }) {
  const outerR = size;
  const innerR = size * 0.28;
  const points: string[] = [];
  for (let i = 0; i < 8; i++) {
    const ang = (i * 45 - 90) * (Math.PI / 180);
    const r = i % 2 === 0 ? outerR : innerR;
    points.push(`${cx + r * Math.cos(ang)},${cy + r * Math.sin(ang)}`);
  }
  return (
    <polygon
      points={points.join(' ')}
      fill="none"
      stroke="var(--natal-accent)"
      strokeWidth={0.8}
    />
  );
}

/**
 * Tier 1 side figure: a large decorative version of the zodiac glyph for the
 * sun sign (left) or rising sign (right), with ornamental flourishes. Tier 2
 * will replace this with bespoke line-art illustrations per sign.
 */
export function SideFigure({ sign, side }: Props) {
  const x = side === 'left' ? 82 : 918;
  const y = 540;

  return (
    <g data-part="side-figure" data-side={side} data-sign={sign}>
      {/* Top-bracket hairline stem */}
      <line
        x1={x}
        x2={x}
        y1={y - 200}
        y2={y - 130}
        stroke="var(--natal-dim)"
        strokeWidth={1}
      />
      <AccentStar cx={x} cy={y - 115} size={5} />

      {/* Large glyph — full SVG icon */}
      <image
        href={zodiacIconUrl(sign)}
        x={x - 48}
        y={y - 48}
        width={96}
        height={96}
        className={styles.glyphText}
        opacity={0.9}
      />

      {/* Small dot flourishes beside the glyph */}
      {[-58, -44, 44, 58].map((dx) => (
        <circle
          key={dx}
          cx={x + dx}
          cy={y}
          r={1}
          fill="var(--natal-accent)"
          opacity={0.7}
        />
      ))}

      {/* Bottom flourish: accent star + hairline + sign name */}
      <AccentStar cx={x} cy={y + 115} size={5} />
      <line
        x1={x - 30}
        x2={x + 30}
        y1={y + 138}
        y2={y + 138}
        stroke="var(--natal-dim)"
        strokeWidth={1}
      />
      <text
        x={x}
        y={y + 160}
        textAnchor="middle"
        dominantBaseline="hanging"
        fontSize={11}
        fill="var(--natal-primary)"
        className={styles.bodyText}
        opacity={0.8}
      >
        {ZODIAC_LABEL[sign].toUpperCase()}
      </text>
      <text
        x={x}
        y={y + 180}
        textAnchor="middle"
        dominantBaseline="hanging"
        fontSize={9}
        fill="var(--natal-primary)"
        className={styles.bodyText}
        opacity={0.5}
      >
        {side === 'left' ? 'SOLAR' : 'ASCENDING'}
      </text>
      <line
        x1={x}
        x2={x}
        y1={y + 205}
        y2={y + 240}
        stroke="var(--natal-dim)"
        strokeWidth={1}
      />
    </g>
  );
}
