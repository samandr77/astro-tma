import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useHaptic } from "@/hooks/useTelegram";
import { MeaningText } from "@/components/ui/MeaningText";
import type { TarotCardDetail } from "@/types";
import {
  CARD_H,
  CARD_W,
  SLOT_H,
  SLOT_W,
  SPREAD_CONFIG,
  type SpreadKey,
} from "@/data/spread-config";

const SLOT_OFFSET_X = (SLOT_W - CARD_W) / 2;
const SLOT_OFFSET_Y = (SLOT_H - CARD_H) / 2;

interface Props {
  spreadType: string;
  cards: TarotCardDetail[];
  placedCount?: number;
  onAllFlipped?: () => void;
}

export function SpreadLayout({
  spreadType,
  cards,
  placedCount,
  onAllFlipped,
}: Props) {
  const { impact } = useHaptic();
  const [revealedCount, setRevealedCount] = useState(0);
  const [isAutoRevealing, setIsAutoRevealing] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [scale, setScale] = useState(1);
  const detailRef = useRef<HTMLDivElement>(null);
  const areaRef = useRef<HTMLDivElement>(null);

  const config = SPREAD_CONFIG[spreadType as SpreadKey];
  const layout = config?.layout;
  const slots =
    config?.layout.slots.map((slot, idx) => {
      const position = config.sections.flatMap((s) => s.positions)[idx];
      return {
        ...slot,
        slot: idx + 1,
        label: position?.label ?? String(idx + 1),
        symbol: config.previewSymbols?.[idx] ?? String(idx + 1),
      };
    }) ?? [];

  useEffect(() => {
    if (onAllFlipped && cards.length > 0 && revealedCount === cards.length) {
      onAllFlipped();
    }
  }, [revealedCount, cards.length, onAllFlipped]);

  useEffect(() => {
    if (!isAutoRevealing) return;
    if (revealedCount >= cards.length) {
      setIsAutoRevealing(false);
      return;
    }
    const t = setTimeout(
      () => setRevealedCount((count) => Math.min(count + 1, cards.length)),
      revealedCount === 0 ? 120 : 420,
    );
    return () => clearTimeout(t);
  }, [isAutoRevealing, revealedCount, cards.length]);

  useEffect(() => {
    if (!layout) return;

    const el = areaRef.current;
    if (!el) return;

    const update = () => {
      const avail = el.clientWidth;
      if (!avail) return;
      setScale(Math.min(1, avail / layout.w));
    };

    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);

    return () => ro.disconnect();
  }, [layout]);

  if (!layout) return null;

  const handleStartReveal = () => {
    if (isAutoRevealing || revealedCount >= cards.length) return;
    impact("medium");
    setIsAutoRevealing(true);
  };

  const handleSelect = (idx: number) => {
    if (idx >= revealedCount) return;
    setSelected(idx);
    setTimeout(() => {
      detailRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }, 120);
  };

  const selectedCard = selected !== null ? cards[selected] : null;
  const selectedSlot = selected !== null ? slots[selected] : null;
  const isAllRevealed = revealedCount >= cards.length;
  const isRevealCta = !isAllRevealed && !isAutoRevealing;

  return (
    <div className={`spread-layout spread-layout--${spreadType}`}>
      <p className={`fan-prompt${isRevealCta ? " fan-prompt--cta" : ""}`}>
        {isAllRevealed
          ? "Расклад открыт"
          : isAutoRevealing
            ? "Карты открываются..."
            : "Нажмите один раз, чтобы открыть карты по порядку"}
      </p>
      <div className="spread-area" ref={areaRef}>
        <div
          className="spread-fit"
          style={{ width: layout.w * scale, height: layout.h * scale }}
        >
          <div
            className="spread-container"
            style={{
              width: layout.w,
              height: layout.h,
              transform: `scale(${scale})`,
            }}
          >
            {slots.map((slot, idx) => {
              const card = cards[idx];
              const isPlaced =
                placedCount === undefined ? !!card : idx < placedCount;
              const isFlipped = idx < revealedCount;
              const isSelected = selected === idx;
              const isCross = !!slot.rotate;
              const label = null;

              if (!isPlaced) {
                return (
                  <div
                    key={slot.slot}
                    className={`spread-slot spread-slot--empty${
                      isCross ? " spread-slot--cross" : ""
                    }`}
                    style={{
                      left: slot.x + SLOT_OFFSET_X,
                      top: slot.y + SLOT_OFFSET_Y,
                      width: CARD_W,
                      height: CARD_H,
                    }}
                  >
                    <div
                      className="spread-slot__rotor"
                      style={
                        isCross
                          ? { transform: `rotate(${slot.rotate}deg)` }
                          : undefined
                      }
                    >
                      <div className="spread-slot__placeholder">
                        <span className="spread-slot__placeholder-num">
                          {slot.slot}
                        </span>
                      </div>
                    </div>
                    {label}
                  </div>
                );
              }

              if (!card) return null;

              return (
                <motion.div
                  key={slot.slot}
                  className={`spread-slot${
                    isCross ? " spread-slot--cross" : ""
                  }${isSelected ? " spread-slot--selected" : ""}`}
                  style={{
                    left: slot.x + SLOT_OFFSET_X,
                    top: slot.y + SLOT_OFFSET_Y,
                    width: CARD_W,
                    height: CARD_H,
                  }}
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.3 }}
                  onClick={() => {
                    if (isAllRevealed) handleSelect(idx);
                    else handleStartReveal();
                  }}
                >
                  <div
                    className="spread-slot__rotor"
                    style={
                      isCross
                        ? { transform: `rotate(${slot.rotate}deg)` }
                        : undefined
                    }
                  >
                    <div
                      className={`spread-slot__flipper${
                        isFlipped ? " is-flipped" : ""
                      }`}
                    >
                      <div className="spread-slot__back">
                        <span className="spread-slot__number">
                          {slot.slot}
                        </span>
                      </div>
                      <div className="spread-slot__front">
                        {card.image_url ? (
                          <img
                            src={card.image_url}
                            alt={card.name_ru}
                            className={`spread-slot__img${
                              card.reversed ? " spread-slot__img--reversed" : ""
                            }`}
                            loading="lazy"
                          />
                        ) : (
                          <span className="spread-slot__emoji">
                            {card.emoji}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  {label}
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>

      <div ref={detailRef}>
        <AnimatePresence mode="wait">
          {selectedCard && selectedSlot && selected !== null && selected < revealedCount && (
            <motion.div
              key={selected}
              className="spread-detail"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.3 }}
            >
              <div className="spread-detail__header">
                <span className="spread-detail__pos">
                  {selectedSlot.slot}. {selectedSlot.label}
                </span>
                <span
                  className={`spread-detail__orient${
                    selectedCard.reversed ? " rev" : ""
                  }`}
                >
                  {selectedCard.reversed ? "↓ Перевёрнутая" : "↑ Прямая"}
                </span>
              </div>
              <h3 className="spread-detail__name">{selectedCard.name_ru}</h3>
              <p className="spread-detail__keys">
                {selectedCard.keywords_ru?.slice(0, 3).join(" · ")}
              </p>
              <MeaningText text={selectedCard.meaning_ru} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
