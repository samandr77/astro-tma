import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { useMutation } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { tarotApi } from "@/services/api";
import { useHaptic } from "@/hooks/useTelegram";
import { MeaningText } from "@/components/ui/MeaningText";
import { TarotCardBack } from "@/components/tarot/TarotCardBack";
import { SpreadReading } from "@/components/tarot/SpreadReading";
import type { TarotCardDetail } from "@/types";

const POSITIONS = ["Прошлое", "Настоящее", "Будущее"];
const FAN_COUNT = 9;
const FLY_W = 180; // revealed card width
const FLY_H = 270; // revealed card height
const SLOT_W = 86;
const SLOT_H = 126;
const FAN_CARD_W = 92;
const CARD_SCALE = FAN_CARD_W / FLY_W;
const EASE = [0.22, 0.61, 0.36, 1] as const;

type Phase = "spinning" | "fly-in" | "revealed" | "fly-out" | "reading";

// ── Pre-compute fan positions ──────────────────────────────────────────────
const FAN_POS = Array.from({ length: FAN_COUNT }, (_, i) => {
  const center = (FAN_COUNT - 1) / 2;
  const offset = i - center;
  const abs = Math.abs(offset);
  return {
    i,
    x: offset * 42,
    y: abs * 13 + (offset === 0 ? -42 : 0),
    angleDeg: offset * 10,
    z: 20 - abs,
  };
});

// ── Card back face ─────────────────────────────────────────────────────────
function CardBack({ large = false }: { large?: boolean }) {
  return (
    <div
      className={`tarot-card-back ${large ? "tarot-card-back--large" : ""}`}
      style={{ width: "100%", height: "100%" }}
    >
      <TarotCardBack />
    </div>
  );
}

// ── Card front face (parchment or image) ───────────────────────────────────
function CardFront({ card }: { card: TarotCardDetail }) {
  if (card.image_url) {
    return (
      <img
        src={card.image_url}
        alt={card.name_ru}
        className={`tarot-card-front__img${card.reversed ? " tarot-card-front__img--reversed" : ""}`}
      />
    );
  }
  return (
    <div className="tarot-card-front__parchment">
      <span className="tarot-card-front__number">
        {card.arcana === "major" ? `${card.id}` : ""}
      </span>
      <span className="tarot-card-front__symbol">{card.emoji}</span>
      <span className="tarot-card-front__name">{card.name_ru}</span>
    </div>
  );
}

interface ThreeCardFlowProps {
  onProgressChange?: (inProgress: boolean) => void;
}

// ── Main component ──────────────────────────────────────────────────────────
export function ThreeCardFlow({ onProgressChange }: ThreeCardFlowProps = {}) {
  const { impact } = useHaptic();
  const [phase, setPhase] = useState<Phase>("spinning");
  const [drawnCount, setDrawnCount] = useState(0);
  const [landedSlots, setLandedSlots] = useState<number[]>([]);
  const [flyFrom, setFlyFrom] = useState<{ x: number; y: number } | null>(null);
  const [flyTo, setFlyTo] = useState<{ x: number; y: number } | null>(null);
  const [showOverlay, setShowOverlay] = useState(false);
  const [showGlow, setShowGlow] = useState(false);
  const [showText, setShowText] = useState(false);
  const [showContinue, setShowContinue] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const [shownCards, setShownCards] = useState<number[]>([]);
  const [isAutoShowing, setIsAutoShowing] = useState(false);

  const slotRef0 = useRef<HTMLDivElement>(null);
  const slotRef1 = useRef<HTMLDivElement>(null);
  const slotRef2 = useRef<HTMLDivElement>(null);
  const slotRefs = useMemo(() => [slotRef0, slotRef1, slotRef2], []);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const drawMutation = useMutation({
    mutationFn: () => tarotApi.draw("three_card"),
    onError: (err) => {
      // 429 = monthly rate limit hit — surface the server message.
      const message = err instanceof Error ? err.message : String(err);
      if (typeof window !== "undefined" && window.alert) {
        // Telegram WebApp.showAlert can't be required here without dragging
        // the @twa-dev/sdk import into this file; native confirm/alert is
        // good enough on TMA + desktop.
        window.alert(message);
      }
    },
  });
  const apiCards = drawMutation.data?.cards ?? [];
  const apiReady = apiCards.length >= 3;

  useEffect(() => {
    drawMutation.mutate();
  }, []); // eslint-disable-line
  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
      onProgressChange?.(false);
    },
    [], // eslint-disable-line
  );

  useEffect(() => {
    if (!onProgressChange) return;
    const active =
      phase === "fly-in" ||
      phase === "revealed" ||
      phase === "fly-out" ||
      (phase === "spinning" && drawnCount > 0);
    onProgressChange(active);
  }, [phase, drawnCount, onProgressChange]);

  // Card center position on screen (revealed state)
  // Clamp Y so the card + reveal-info block never sits under the bottom nav.
  const cardPos = useMemo(() => {
    const navGap = 140; // nav height + reveal info + padding
    const preferredY = window.innerHeight * 0.34 - FLY_H / 2;
    const maxY = window.innerHeight - FLY_H - navGap;
    return {
      x: Math.round(window.innerWidth / 2 - FLY_W / 2),
      y: Math.round(Math.min(preferredY, maxY)),
    };
  }, []);

  const currentCard = apiCards[drawnCount] ?? null;

  // ── Wheel click ───────────────────────────────────────────────────────────
  const handleCardClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (phase !== "spinning" || !apiReady || drawnCount >= 3) return;
      e.stopPropagation();
      impact("medium");

      const rect = e.currentTarget.getBoundingClientRect();
      // Center of clicked card
      setFlyFrom({
        x: rect.left + rect.width / 2,
        y: rect.top + rect.height / 2,
      });
      setPhase("fly-in");

      // Timing sequence (all from click)
      const push = (fn: () => void, ms: number) => {
        const t = setTimeout(fn, ms);
        timers.current.push(t);
      };
      push(() => setShowOverlay(true), 200);
      push(() => setShowGlow(true), 2000);
      // 2900ms: fly ends → onFlyInComplete fires (via onAnimationComplete)
    },
    [phase, apiReady, drawnCount, impact],
  );

  const onFlyInComplete = useCallback(() => {
    setPhase("revealed");
    const push = (fn: () => void, ms: number) => {
      const t = setTimeout(fn, ms);
      timers.current.push(t);
    };
    push(() => setShowText(true), 300);
    push(() => setShowContinue(true), 700);
  }, []);

  // ── Continue button ───────────────────────────────────────────────────────
  const handleContinue = useCallback(() => {
    impact("light");
    const rect = slotRefs[drawnCount].current?.getBoundingClientRect();
    setFlyTo({
      x: rect
        ? rect.left - (FLY_W - SLOT_W) / 2
        : window.innerWidth / 2 - FLY_W / 2,
      y: rect ? rect.top - (FLY_H - SLOT_H) / 2 : window.innerHeight - 200,
    });
    setShowText(false);
    setShowContinue(false);
    setShowGlow(false);
    setShowOverlay(false);
    setPhase("fly-out");
  }, [drawnCount, slotRefs, impact]);

  const onFlyOutComplete = useCallback(() => {
    const next = drawnCount + 1;
    setLandedSlots((prev) => [...prev, drawnCount]);
    setDrawnCount(next);
    setFlyFrom(null);
    setFlyTo(null);
    setPhase(next >= 3 ? "reading" : "spinning");
  }, [drawnCount]);

  useEffect(() => {
    if (phase !== "reading" || !isAutoShowing) return;
    if (shownCards.length >= 3) {
      setIsAutoShowing(false);
      return;
    }
    const t = setTimeout(() => {
      setShownCards((prev) =>
        prev.length >= 3 ? prev : [...prev, prev.length],
      );
    }, shownCards.length === 0 ? 120 : 420);
    timers.current.push(t);
    return () => clearTimeout(t);
  }, [phase, isAutoShowing, shownCards.length]);

  // ── Reading phase card tap ────────────────────────────────────────────────
  const handleCardTap = useCallback(
    (idx: number) => {
      if (phase !== "reading") return;
      if (shownCards.length < 3) {
        impact("medium");
        setIsAutoShowing(true);
        return;
      }
      if (expandedIdx === idx) {
        setExpandedIdx(null);
        setShownCards((prev) => (prev.includes(idx) ? prev : [...prev, idx]));
      } else {
        impact("medium");
        setExpandedIdx(idx);
      }
    },
    [phase, shownCards.length, expandedIdx, impact],
  );

  // Derived state for wheel appearance
  const isWheelSpinning = phase === "spinning" || phase === "fly-out";
  const cardsVisible = isWheelSpinning || phase === "reading";
  const isFlying =
    phase === "fly-in" || phase === "revealed" || phase === "fly-out";

  // Fly-in initial position (center of clicked card, scaled down)
  const flyInitial = flyFrom
    ? {
        x: flyFrom.x - FLY_W / 2,
        y: flyFrom.y - FLY_H / 2,
        scale: CARD_SCALE,
      }
    : null;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="three-flow">
      {/* ══ FAN SCENE ══ */}
      {/* stays mounted even at reading phase — the remaining deck is visible behind the reading */}
      <motion.div
        key="wheel-scene"
        className={`wheel-scene${phase === "reading" ? " wheel-scene--mini" : ""}`}
        animate={{
          opacity: phase === "reading" ? 0.28 : 1,
          scale: phase === "reading" ? 0.55 : 1,
        }}
        transition={{ duration: 0.45, ease: [0.22, 0.61, 0.36, 1] }}
        style={
          phase === "reading" ? { pointerEvents: "none" as const } : undefined
        }
      >
        {/* Title (only when spinning) */}
        <AnimatePresence>
          {isWheelSpinning && (
            <motion.div
              key="wheel-title"
              className="wheel-scene__header"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.4 }}
            >
              <h3 className="wheel-scene__title">Выберите 3 карты</h3>
              <p className="wheel-scene__subtitle">
                Первая — прошлое, вторая — настоящее, третья — будущее
              </p>
              <motion.p
                className="wheel-pick-note"
                animate={{
                  opacity: apiReady ? [0.72, 1, 0.72] : [0.46, 0.72, 0.46],
                }}
                transition={{
                  duration: 2.2,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              >
                {!apiReady
                  ? "Готовим карты"
                  : `Шаг ${drawnCount + 1}/3 · ${POSITIONS[drawnCount]}`}
              </motion.p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Fan */}
        <div className="wheel-outer">
          <div className="wheel-ring">
            {FAN_POS.map(({ i, x, y, angleDeg, z }) => (
              <div
                key={i}
                className={`wheel-card${!cardsVisible ? " is-hidden" : ""}`}
                style={{
                  "--fan-x": `${x}px`,
                  "--fan-y": `${y}px`,
                  "--fan-rot": `${angleDeg}deg`,
                  zIndex: z,
                } as React.CSSProperties}
                onClick={handleCardClick}
              >
                <CardBack />
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* ══ SLOTS (all phases) ══ */}
      <div
        className={`wheel-slots${phase === "reading" ? " wheel-slots--reading" : ""}`}
      >
        {POSITIONS.map((pos, i) => {
          const hasLanded = landedSlots.includes(i);
          const card = apiCards[i];
          return (
            <div key={i} className="wheel-slot">
              <div
                ref={slotRefs[i]}
                className={`wheel-slot__box${phase === "reading" ? " is-reading" : ""}`}
              >
                {hasLanded ? (
                  <motion.div
                    className="wheel-slot__card"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2 }}
                    onClick={() => handleCardTap(i)}
                    style={{
                      cursor: phase === "reading" ? "pointer" : "default",
                    }}
                    whileTap={phase === "reading" ? { scale: 0.93 } : undefined}
                  >
                    {card && card.image_url ? (
                      <img
                        src={card.image_url}
                        alt={card.name_ru}
                        className={`slot-card__img${card.reversed ? " slot-card__img--reversed" : ""}`}
                      />
                    ) : card ? (
                      <div className="slot-card__emoji">{card.emoji}</div>
                    ) : (
                      <div className="card-back-skin" />
                    )}
                  </motion.div>
                ) : (
                  <div className="wheel-slot__empty">
                    <span className="slot-number">{i + 1}</span>
                  </div>
                )}
              </div>
              <span className="wheel-slot__label">{pos}</span>
            </div>
          );
        })}
      </div>

      {/* ══ READING CONTENT ══ */}
      <AnimatePresence>
        {phase === "reading" && (
          <motion.div
            key="reading"
            className="reading-content"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
          >
            {shownCards.length === 0 && (
              <motion.p
                className="three-flow__hint"
                onClick={() => setIsAutoShowing(true)}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.6 }}
              >
                Нажмите один раз, чтобы открыть карты по порядку
              </motion.p>
            )}
            <div className="reading-meanings">
              <AnimatePresence>
                {shownCards.map((idx) => {
                  const card = apiCards[idx];
                  if (!card) return null;
                  return (
                    <motion.div
                      key={idx}
                      className="meaning-block"
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      <div className="meaning-block__header">
                        <span className="meaning-block__pos">
                          {POSITIONS[idx]}
                        </span>
                        <span
                          className={`meaning-block__orient${card.reversed ? " rev" : ""}`}
                        >
                          {card.reversed ? "↓" : "↑"}
                        </span>
                        <span className="meaning-block__name">
                          {card.name_ru}
                        </span>
                      </div>
                      <p className="meaning-block__keys">
                        {card.keywords_ru?.slice(0, 3).join(" · ")}
                      </p>
                      <MeaningText text={card.meaning_ru} />
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
            {shownCards.length === 3 && drawMutation.data && (
              <SpreadReading
                spreadType="three_card"
                readingId={drawMutation.data.reading_id}
                cards={apiCards}
              />
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ══ DARK OVERLAY (z-index 10) ══ */}
      <AnimatePresence>
        {isFlying && showOverlay && (
          <motion.div
            key="fly-overlay"
            className="fly-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: phase === "fly-out" ? 0 : 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.8 }}
          />
        )}
      </AnimatePresence>

      {/* ══ GOLD GLOW (z-index 10, behind card) ══ */}
      <AnimatePresence>
        {(phase === "fly-in" || phase === "revealed") && showGlow && (
          <motion.div
            key="glow"
            style={{
              position: "fixed",
              left: cardPos.x + FLY_W / 2 - 110,
              top: cardPos.y + FLY_H / 2 - 110,
              width: 220,
              height: 220,
              borderRadius: "50%",
              background:
                "radial-gradient(circle, rgba(201,168,76,0.10) 0%, rgba(201,168,76,0.02) 40%, transparent 70%)",
              zIndex: 10, // overlay
              pointerEvents: "none",
            }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1, ease: "easeOut" }}
          />
        )}
      </AnimatePresence>

      {/* ══ FLY-IN CARD (z-index 11) ══ */}
      <AnimatePresence>
        {phase === "fly-in" && flyInitial && (
          <motion.div
            key="fly-in-card"
            className="tarot-card-frame"
            style={{
              position: "fixed",
              left: 0,
              top: 0,
              width: FLY_W,
              height: FLY_H,
              zIndex: 20,
              pointerEvents: "none",
            }}
            initial={flyInitial}
            animate={{ x: cardPos.x, y: cardPos.y, scale: 1 }}
            transition={{ duration: 2.5, ease: EASE, delay: 0.4 }}
            onAnimationComplete={onFlyInComplete}
          >
            {/* Perspective wrapper for 3D flip */}
            <div
              style={{
                perspective: "900px",
                width: "100%",
                height: "100%",
                overflow: "hidden",
                borderRadius: "inherit",
              }}
            >
              <motion.div
                style={{
                  transformStyle: "preserve-3d",
                  width: "100%",
                  height: "100%",
                  position: "relative",
                }}
                initial={{ rotateY: 0 }}
                animate={{ rotateY: 180 }}
                transition={{ duration: 2.5, ease: EASE, delay: 0.4 }}
              >
                {/* Back face */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    backfaceVisibility: "hidden",
                    borderRadius: "inherit",
                    overflow: "hidden",
                  }}
                >
                  <CardBack large />
                </div>
                {/* Front face */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    backfaceVisibility: "hidden",
                    transform: "rotateY(180deg)",
                    borderRadius: "inherit",
                    overflow: "hidden",
                  }}
                >
                  {currentCard && <CardFront card={currentCard} />}
                </div>
              </motion.div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ══ REVEALED CARD (static, z-index 11) ══ */}
      {phase === "revealed" && currentCard && (
        <div
          className="tarot-card-frame"
          style={{
            position: "fixed",
            left: cardPos.x,
            top: cardPos.y,
            width: FLY_W,
            height: FLY_H,
            zIndex: 20, // flying card
          }}
        >
          <CardFront card={currentCard} />
        </div>
      )}

      {/* ══ FLY-OUT CARD (z-index 11) ══ */}
      <AnimatePresence>
        {phase === "fly-out" && flyTo && currentCard && (
          <motion.div
            key="fly-out-card"
            className="tarot-card-frame"
            style={{
              position: "fixed",
              left: 0,
              top: 0,
              width: FLY_W,
              height: FLY_H,
              zIndex: 20,
              pointerEvents: "none",
            }}
            initial={{ x: cardPos.x, y: cardPos.y, scale: 1 }}
            animate={{ x: flyTo.x, y: flyTo.y, scale: SLOT_W / FLY_W }}
            transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
            onAnimationComplete={onFlyOutComplete}
          >
            <CardFront card={currentCard} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ══ CARD NAME + MEANING + CONTINUE (z-index 12) ══ */}
      <AnimatePresence>
        {phase === "revealed" && currentCard && (
          <motion.div
            key="reveal-info"
            className="reveal-info"
            style={{ top: cardPos.y + FLY_H + 18 }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <AnimatePresence>
              {showText && (
                <motion.div
                  className="reveal-info__text"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.8 }}
                >
                  <p className="reveal-info__name">
                    {currentCard.name_ru}
                    {currentCard.reversed && (
                      <span className="reveal-info__rev"> (Перевёрнутая)</span>
                    )}
                  </p>
                  <p className="reveal-info__keys">
                    {currentCard.keywords_ru?.slice(0, 3).join(", ")}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
            <AnimatePresence>
              {showContinue && (
                <motion.button
                  className="reveal-info__continue-btn"
                  onClick={handleContinue}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6 }}
                  whileTap={{ scale: 0.96 }}
                >
                  {drawnCount === 2 ? "Читать расклад" : "Продолжить"}
                </motion.button>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ══ READING EXPANDED OVERLAY ══ */}
      <AnimatePresence>
        {expandedIdx !== null &&
          phase === "reading" &&
          (() => {
            const card = apiCards[expandedIdx];
            if (!card) return null;
            return (
              <motion.div
                key="expanded"
                className="reveal-overlay"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.22 }}
                onClick={() => handleCardTap(expandedIdx)}
              >
                <motion.div
                  className="reveal-card"
                  initial={{ scale: 0.45, opacity: 0, y: 40 }}
                  animate={{ scale: 1, opacity: 1, y: 0 }}
                  exit={{ scale: 0.45, opacity: 0, y: 40 }}
                  transition={{ type: "spring", damping: 22, stiffness: 260 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="reveal-card__img-wrap">
                    {card.image_url ? (
                      <img
                        src={card.image_url}
                        alt={card.name_ru}
                        className="reveal-card__img"
                      />
                    ) : (
                      <div className="reveal-card__emoji-fallback">
                        {card.emoji}
                      </div>
                    )}
                  </div>
                  <div className="reveal-card__info">
                    <p className="reveal-card__arcana">
                      {card.arcana === "major"
                        ? "Старший аркан"
                        : "Младший аркан"}
                    </p>
                    <h3 className="reveal-card__name">{card.name_ru}</h3>
                    <p
                      className={`reveal-card__orient${card.reversed ? " rev" : ""}`}
                    >
                      {card.reversed ? "↓ Перевёрнутое" : "↑ Прямое"}
                    </p>
                    <p className="reveal-card__keys">
                      {card.keywords_ru?.slice(0, 3).join(" · ")}
                    </p>
                    <button
                      className="btn-ghost reveal-card__close"
                      onClick={() => handleCardTap(expandedIdx)}
                    >
                      Вернуть карту
                    </button>
                  </div>
                </motion.div>
              </motion.div>
            );
          })()}
      </AnimatePresence>
    </div>
  );
}
