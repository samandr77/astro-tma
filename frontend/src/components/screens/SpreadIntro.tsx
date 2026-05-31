import { useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import { motion } from "framer-motion";
import {
  SPREAD_CONFIG,
  CARD_W,
  CARD_H,
  SLOT_W,
  SLOT_H,
  type SpreadKey,
} from "@/data/spread-config";

interface Props {
  spreadKey: SpreadKey;
  onStart: () => void;
}

function ThreeCardIntro({ onStart }: { onStart: () => void }) {
  const config = SPREAD_CONFIG.three_card;
  const positions = config.sections[0]?.positions ?? [];

  return (
    <motion.div
      className="spread-intro-v2 spread-intro-v2--showcase spread-intro-v2--three_card spread-intro-v2--three-ref"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <h1 className="spread-intro-v2__title spread-intro-v2__title--three">
        {config.title}
      </h1>

      <div className="spread-intro-v2__three-preview">
        {positions.map((pos) => (
          <div key={pos.num} className="spread-intro-v2__back-card">
            <div className="spread-intro-v2__back-badge">{pos.num}</div>
          </div>
        ))}
      </div>

      <div className="spread-intro-v2__frame spread-intro-v2__frame--three">
        <p
          className="spread-intro-v2__story"
          dangerouslySetInnerHTML={{ __html: config.intro }}
        />
      </div>

      <motion.button
        className="btn-primary spread-intro-v2__start-btn"
        onClick={onStart}
        whileTap={{ scale: 0.96 }}
      >
        Перейти к раскладу
      </motion.button>
    </motion.div>
  );
}

export function SpreadIntro({ spreadKey, onStart }: Props) {
  const [titleScale, setTitleScale] = useState(1);
  const titleWrapRef = useRef<HTMLHeadingElement>(null);
  const titleMeasureRef = useRef<HTMLSpanElement>(null);

  const config = SPREAD_CONFIG[spreadKey];
  const { layout, title } = config;
  const previewCardW = CARD_W;
  const titleStyle = {
    "--spread-title-scale": titleScale,
  } as CSSProperties;

  useLayoutEffect(() => {
    const titleWrap = titleWrapRef.current;
    const titleMeasure = titleMeasureRef.current;
    if (!titleWrap || !titleMeasure) return;

    let frame = 0;
    const updateScale = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const availableWidth = titleWrap.clientWidth;
        const naturalWidth = titleMeasure.scrollWidth;
        const nextScale =
          availableWidth > 0 && naturalWidth > 0
            ? Math.min(1, availableWidth / naturalWidth)
            : 1;

        setTitleScale((current) =>
          Math.abs(current - nextScale) > 0.005 ? nextScale : current,
        );
      });
    };

    updateScale();
    window.addEventListener("resize", updateScale);

    const resizeObserver =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(updateScale)
        : null;
    resizeObserver?.observe(titleWrap);
    resizeObserver?.observe(titleMeasure);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", updateScale);
      resizeObserver?.disconnect();
    };
  }, [title]);

  if (spreadKey === "three_card") {
    return <ThreeCardIntro onStart={onStart} />;
  }

  return (
    <motion.div
      className={`spread-intro-v2 spread-intro-v2--showcase spread-intro-v2--${spreadKey}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <h1
        ref={titleWrapRef}
        className="spread-intro-v2__title"
        style={titleStyle}
      >
        <span className="spread-intro-v2__title-text">{title}</span>
        <span
          ref={titleMeasureRef}
          className="spread-intro-v2__title-measure"
          aria-hidden="true"
        >
          {title}
        </span>
      </h1>

      <div className="spread-intro-v2__preview spread-intro-v2__preview--ornament">
        <svg
          className="spread-intro-v2__preview-svg"
          viewBox={`0 0 ${layout.w} ${layout.h}`}
          preserveAspectRatio="xMidYMid meet"
          xmlns="http://www.w3.org/2000/svg"
        >
          {layout.slots.map((slot, idx) => {
            const number = idx + 1;
            const cx = slot.x + SLOT_W / 2;
            const cy = slot.y + SLOT_H / 2;
            const imageX = cx - previewCardW / 2;
            const transform = slot.rotate
              ? `rotate(${slot.rotate} ${cx} ${cy})`
              : undefined;
            return (
              <g key={idx} transform={transform}>
                <image
                  href="/tarot-back.jpg"
                  x={imageX}
                  y={cy - CARD_H / 2}
                  width={previewCardW}
                  height={CARD_H}
                  preserveAspectRatio="xMidYMid meet"
                />
                <g transform={`translate(${cx} ${cy})`} pointerEvents="none">
                  <text
                    x="0"
                    y="0"
                    dy="0.05em"
                    textAnchor="middle"
                    dominantBaseline="central"
                    alignmentBaseline="middle"
                    fontFamily="Cormorant Garamond, Georgia, serif"
                    fontWeight={700}
                    fontSize={15}
                    fontVariant="tabular-nums"
                    style={{ fontFeatureSettings: "'tnum' 1, 'lnum' 1" }}
                    fill="#151007"
                    stroke="#e8d29e"
                    strokeWidth={0.28}
                    paintOrder="stroke"
                  >
                    {number}
                  </text>
                </g>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="spread-intro-v2__frame">
        <p
          className="spread-intro-v2__story"
          dangerouslySetInnerHTML={{ __html: config.intro }}
        />
      </div>

      <motion.button
        className="btn-primary spread-intro-v2__start-btn"
        onClick={onStart}
        whileTap={{ scale: 0.96 }}
      >
        Перейти к раскладу
      </motion.button>
    </motion.div>
  );
}
