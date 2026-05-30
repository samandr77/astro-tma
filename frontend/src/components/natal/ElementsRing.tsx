import type { NatalElementKey } from "@/types";

const SIZE = 180;
const RADIUS = 70;
const STROKE = 22;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const COLORS: Record<NatalElementKey, string> = {
  fire: "#e88b8b",
  earth: "#8bc89b",
  air: "#c5d4e8",
  water: "#8bb4e8",
};

interface ElementsRingProps {
  fire: number;
  earth: number;
  air: number;
  water: number;
  dominantLabel: string;
  dominantPercent: number;
  onSegmentClick?: (element: NatalElementKey) => void;
}

const ORDER: NatalElementKey[] = ["fire", "earth", "air", "water"];

export function ElementsRing({
  fire,
  earth,
  air,
  water,
  dominantLabel,
  dominantPercent,
  onSegmentClick,
}: ElementsRingProps) {
  const values: Record<NatalElementKey, number> = { fire, earth, air, water };
  const total = fire + earth + air + water || 1;

  let acc = 0;
  const segments = ORDER.map((key) => {
    const value = values[key];
    const fraction = value / total;
    const length = fraction * CIRCUMFERENCE;
    const offset = -acc;
    acc += length;
    return {
      key,
      length,
      offset,
      color: COLORS[key],
      percent: Math.round(fraction * 100),
    };
  });

  return (
    <div className="natal-elements-ring">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        width={SIZE}
        height={SIZE}
        aria-hidden="true"
      >
        <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth={STROKE}
          />
          {segments.map((s) => (
            <circle
              key={s.key}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke={s.color}
              strokeWidth={STROKE}
              strokeDasharray={`${s.length} ${CIRCUMFERENCE - s.length}`}
              strokeDashoffset={s.offset}
              style={{
                cursor: onSegmentClick ? "pointer" : "default",
                transition: "opacity 0.2s",
              }}
              onClick={() => onSegmentClick?.(s.key)}
            />
          ))}
        </g>
      </svg>
      <div className="natal-elements-ring__center">
        <div className="natal-elements-ring__pct">{dominantPercent}%</div>
        <div className="natal-elements-ring__label">{dominantLabel}</div>
      </div>
    </div>
  );
}

export const ELEMENT_RING_COLORS = COLORS;
