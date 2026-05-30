import type { CSSProperties } from "react";

interface Props {
  className?: string;
  style?: CSSProperties;
  ariaHidden?: boolean;
}

export function TarotCardBackSvg({
  className,
  style,
  ariaHidden = true,
}: Props) {
  return (
    <svg
      className={className}
      style={style}
      viewBox="0 0 68 102"
      preserveAspectRatio="xMidYMid slice"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden={ariaHidden}
    >
      <defs>
        <linearGradient id="tcb-bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2a3aa8" />
          <stop offset="100%" stopColor="#1a236f" />
        </linearGradient>
      </defs>

      <rect width="68" height="102" rx="4" ry="4" fill="url(#tcb-bg)" />
      <rect
        x="2"
        y="2"
        width="64"
        height="98"
        rx="3"
        ry="3"
        fill="none"
        stroke="#7fa9e8"
        strokeWidth="0.6"
      />
      <rect
        x="4"
        y="4"
        width="60"
        height="94"
        rx="2"
        ry="2"
        fill="none"
        stroke="#7fa9e8"
        strokeWidth="0.4"
        opacity="0.7"
      />

      <g stroke="#9bbef0" strokeWidth="0.7" fill="none" strokeLinejoin="round">
        <circle cx="34" cy="51" r="26" opacity="0.85" />
        <circle cx="34" cy="51" r="20" opacity="0.6" />

        <polygon points="34,25 39,51 34,77 29,51" opacity="0.95" />
        <polygon points="8,51 34,46 60,51 34,56" opacity="0.95" />
        <polygon points="16,33 36,49 52,69 32,53" opacity="0.85" />
        <polygon points="52,33 36,53 16,69 32,49" opacity="0.85" />
      </g>

      <g fill="none" stroke="#bcd2f5" strokeWidth="0.5">
        <circle cx="34" cy="51" r="8" />
        <circle cx="34" cy="51" r="5" />
        <path d="M34 43 Q38 51 34 59 Q30 51 34 43 Z" />
        <path d="M26 51 Q34 47 42 51 Q34 55 26 51 Z" />
        <circle cx="34" cy="51" r="1.4" fill="#bcd2f5" />
      </g>

      <g fill="#7fa9e8">
        <circle cx="6" cy="6" r="1.1" />
        <circle cx="62" cy="6" r="1.1" />
        <circle cx="6" cy="96" r="1.1" />
        <circle cx="62" cy="96" r="1.1" />
      </g>
      <g fill="none" stroke="#7fa9e8" strokeWidth="0.5" strokeLinecap="round">
        <path d="M3 12 Q8 12 8 7" />
        <path d="M65 12 Q60 12 60 7" />
        <path d="M3 90 Q8 90 8 95" />
        <path d="M65 90 Q60 90 60 95" />
      </g>
    </svg>
  );
}
