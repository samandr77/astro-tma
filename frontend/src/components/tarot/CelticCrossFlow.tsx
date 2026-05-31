import { useState, useRef, useEffect, useCallback } from 'react'
import { FanOfCards, type FanCard } from './FanOfCards'
import { FlipCard } from './FlipCard'
import { SpreadReading } from './SpreadReading'
import { TarotCardBack } from './TarotCardBack'
import { useHaptic } from '@/hooks/useTelegram'
import type { TarotCardDetail } from '@/types'
import {
  CARD_H,
  CARD_W,
  FAN_CARD_H,
  FAN_CARD_W,
  SLOT_H,
  SLOT_W,
  SPREAD_CONFIG,
} from '@/data/spread-config'
import styles from './CelticCrossFlow.module.css'

const CONFIG = SPREAD_CONFIG.celtic_cross
const LAYOUT_W = CONFIG.layout.w
const LAYOUT_H = CONFIG.layout.h
const INITIAL_FAN_COUNT = 15
const FLY_TO_SLOT_SCALE = CARD_H / FAN_CARD_H
const SLOT_OFFSET_X = (SLOT_W - CARD_W) / 2
const SLOT_OFFSET_Y = (SLOT_H - CARD_H) / 2

const SLOTS: { slot: number; x: number; y: number; symbol: string; rotate?: number }[] = [
  ...CONFIG.layout.slots.map((slot, idx) => ({
    slot: idx + 1,
    x: slot.x,
    y: slot.y,
    rotate: slot.rotate,
    symbol: CONFIG.previewSymbols?.[idx] ?? String(idx + 1),
  })),
]

type Phase = 'idle' | 'shuffle' | 'fan' | 'reading' | 'complete'

interface FlyCardState {
  left: number
  top: number
  dx: number
  dy: number
  startRot: number
  targetIdx: number
}

interface PlacedState {
  justLanded: boolean
}

interface Props {
  readingId: number
  cards: TarotCardDetail[]
}

export function CelticCrossFlow({ readingId, cards }: Props) {
  const { impact } = useHaptic()
  const [phase, setPhase] = useState<Phase>('idle')
  const [fanCards, setFanCards] = useState<FanCard[]>([])
  const [placed, setPlaced] = useState<Map<number, PlacedState>>(new Map())
  const [flyCard, setFlyCard] = useState<FlyCardState | null>(null)
  const [revealedCount, setRevealedCount] = useState(0)
  const [isAutoRevealing, setIsAutoRevealing] = useState(false)
  const [selected, setSelected] = useState<number | null>(null)
  const [scale, setScale] = useState(1)

  const areaRef = useRef<HTMLDivElement>(null)
  const slotRefs = useRef<Map<number, HTMLDivElement>>(new Map())
  const detailRef = useRef<HTMLDivElement>(null)

  const placedCount = placed.size
  const isAllPlaced = placedCount >= SLOTS.length
  const isAllRevealed = revealedCount >= SLOTS.length

  // Responsive scale for the 720×720 spread container
  useEffect(() => {
    const el = areaRef.current
    if (!el) return
    const update = () => {
      const avail = el.clientWidth
      if (!avail) return
      setScale(Math.min(1, avail / LAYOUT_W))
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  /* ── Phase transitions ─────────────────────────────────────────────── */

  const handleDeckClick = useCallback(() => {
    if (phase !== 'idle') return
    impact('medium')
    setPhase('shuffle')
    setTimeout(() => {
      setFanCards(
        Array.from({ length: INITIAL_FAN_COUNT }, (_, i) => ({ id: i })),
      )
      setPhase('fan')
    }, 2400)
  }, [phase, impact])

  const handleFanPick = useCallback(
    (id: number, rect: DOMRect, startRot: number) => {
      if (flyCard || placedCount >= SLOTS.length) return

      const targetEl = slotRefs.current.get(placedCount)
      if (!targetEl) return
      const targetRect = targetEl.getBoundingClientRect()

      impact('light')

      // Mark picked card as gone — fan redistributes remaining cards
      setFanCards((prev) =>
        prev.map((c) => (c.id === id ? { ...c, gone: true } : c)),
      )

      // Compute fly start/target centers
      const startCenterX = rect.left + rect.width / 2
      const startCenterY = rect.top + rect.height / 2
      const targetCenterX = targetRect.left + targetRect.width / 2
      const targetCenterY = targetRect.top + targetRect.height / 2

      setFlyCard({
        left: startCenterX - FAN_CARD_W / 2,
        top: startCenterY - FAN_CARD_H / 2,
        dx: targetCenterX - startCenterX,
        dy: targetCenterY - startCenterY,
        startRot,
        targetIdx: placedCount,
      })
    },
    [flyCard, placedCount, impact],
  )

  const handleFlyEnd = useCallback(() => {
    if (!flyCard) return
    const idx = flyCard.targetIdx
    setPlaced((prev) => new Map(prev).set(idx, { justLanded: true }))
    setFlyCard(null)
    // Clear justLanded flag after land animation completes
    setTimeout(() => {
      setPlaced((prev) => {
        const next = new Map(prev)
        next.set(idx, { justLanded: false })
        return next
      })
    }, 500)
  }, [flyCard])

  // fan → reading once all 10 placed
  useEffect(() => {
    if (phase === 'fan' && isAllPlaced) {
      const t = setTimeout(() => setPhase('reading'), 700)
      return () => clearTimeout(t)
    }
  }, [phase, isAllPlaced])

  // reading → complete once all revealed
  useEffect(() => {
    if (phase === 'reading' && isAllRevealed) {
      const t = setTimeout(() => setPhase('complete'), 500)
      return () => clearTimeout(t)
    }
  }, [phase, isAllRevealed])

  useEffect(() => {
    if (!isAutoRevealing || phase !== 'reading') return

    if (isAllRevealed) {
      setIsAutoRevealing(false)
      return
    }

    const t = setTimeout(
      () => setRevealedCount((n) => Math.min(n + 1, SLOTS.length)),
      revealedCount === 0 ? 120 : 420,
    )

    return () => clearTimeout(t)
  }, [isAutoRevealing, phase, isAllRevealed, revealedCount])

  const handleStartReveal = useCallback(() => {
    if (phase !== 'reading') return
    if (isAutoRevealing || isAllRevealed) return
    impact('medium')
    setIsAutoRevealing(true)
  }, [phase, isAutoRevealing, isAllRevealed, impact])

  const handleSlotClick = useCallback(
    (idx: number) => {
      if (phase !== 'complete') return
      if (idx >= revealedCount) return
      setSelected(idx)
      setTimeout(() => {
        detailRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
        })
      }, 200)
    },
    [phase, revealedCount],
  )

  /* ── Render helpers ────────────────────────────────────────────────── */

  const prompt =
    phase === 'idle'
      ? 'Нажмите на колоду, чтобы перемешать карты'
      : phase === 'shuffle'
        ? 'Карты перемешиваются…'
        : phase === 'fan' && !isAllPlaced
          ? placedCount === 0
            ? 'Выберите карту, которую чувствуете'
            : `Выбрано ${placedCount} из ${SLOTS.length}`
          : phase === 'reading' && !isAllRevealed
            ? isAutoRevealing
              ? 'Карты открываются…'
              : 'Нажмите в любом месте, чтобы открыть все карты'
            : ''

  const containerPadded = phase === 'idle' || phase === 'shuffle' || phase === 'fan'
  const isRevealCta =
    phase === 'reading' && !isAllRevealed && !isAutoRevealing
  const showRemainingDeck = phase === 'reading' || phase === 'complete'

  return (
    <div
      className={`${styles.flowContainer} ${containerPadded ? '' : styles.noPad}`}
    >
      {!isRevealCta && (
        <p className={styles.prompt} style={{ minHeight: 20 }}>
          {prompt}
        </p>
      )}

      {/* ── Slot grid (always visible) ── */}
      <div className={styles.spreadArea} ref={areaRef}>
        <div
          className={styles.spreadFit}
          style={{ width: LAYOUT_W * scale, height: LAYOUT_H * scale }}
        >
          <div
            className={styles.spreadContainer}
            style={{
              width: LAYOUT_W,
              height: LAYOUT_H,
              transform: `scale(${scale})`,
            }}
          >
            {SLOTS.map((slot, idx) => {
              const isPlaced = placed.has(idx)
              const isRevealed = idx < revealedCount
              const justLanded = placed.get(idx)?.justLanded
              const isCross = !!slot.rotate
              const card = cards[idx]

              return (
                <div
                  key={slot.slot}
                  className={`${styles.slot} ${isCross ? styles.slotCross : ''}`}
                  ref={(el) => {
                    if (el) slotRefs.current.set(idx, el)
                    else slotRefs.current.delete(idx)
                  }}
                  style={{
                    left: slot.x + SLOT_OFFSET_X,
                    top: slot.y + SLOT_OFFSET_Y,
                    width: CARD_W,
                    height: CARD_H,
                  }}
                  onClick={() =>
                    phase === 'complete' && isRevealed && handleSlotClick(idx)
                  }
                >
                  <div
                    className={styles.rotor}
                    style={
                      isCross
                        ? { transform: `rotate(${slot.rotate}deg)` }
                        : undefined
                    }
                  >
                    {!isPlaced ? (
                      <div
                        className={`${styles.placeholder} ${
                          isCross ? styles.placeholderCross : ''
                        }`}
                      >
                        <span className={styles.placeholderSymbol}>
                          {slot.slot}
                        </span>
                      </div>
                    ) : (
                      <div className={justLanded ? styles.cardLand : ''}>
                        <FlipCard
                          revealed={isRevealed}
                          width={CARD_W}
                          height={CARD_H}
                          back={<TarotCardBack />}
                          front={
                            card?.image_url ? (
                              <img
                                src={card.image_url}
                                alt={card.name_ru}
                                style={{
                                  width: '100%',
                                  height: '100%',
                                  objectFit: 'cover',
                                  display: 'block',
                                  transform: card.reversed
                                    ? 'rotate(180deg)'
                                    : undefined,
                                }}
                              />
                            ) : (
                              <div
                                style={{
                                  width: '100%',
                                  height: '100%',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  fontSize: 28,
                                  background: 'rgba(212,178,84,0.06)',
                                  border: '1.5px solid rgba(212,178,84,0.45)',
                                }}
                              >
                                {card?.emoji}
                              </div>
                            )
                          }
                        />
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {isRevealCta && (
        <p className={styles.promptCta}>{prompt}</p>
      )}

      {/* ── Deck (stays on the table after the draw) ── */}
      {(phase === 'idle' || phase === 'shuffle' || showRemainingDeck) && (
        <div
          className={`${styles.deckWrap} ${
            showRemainingDeck ? styles.deckWrapSettled : ''
          }`}
        >
          {showRemainingDeck ? (
            <div className={styles.remainingDeck} aria-hidden="true">
              {[0, 1, 2].map((i) => (
                <div key={i} className={styles.remainingCard}>
                  <TarotCardBack />
                </div>
              ))}
            </div>
          ) : (
            <div
              className={`${styles.deck} ${phase === 'shuffle' ? styles.deckShuffling : ''}`}
              onClick={handleDeckClick}
            >
              {[3, 2, 1, 0].map((i) => (
                <div
                  key={i}
                  className={styles.deckLayer}
                  style={{
                    left: i * 2,
                    top: i * 2,
                    zIndex: 4 - i,
                    opacity: 0.55 + i * 0.12,
                  }}
                >
                  <TarotCardBack />
                </div>
              ))}
              <div
                className={styles.deckLayer}
                style={{ left: 7, top: 7, zIndex: 10 }}
              >
                <TarotCardBack />
              </div>
            </div>
          )}
          {(phase === 'idle' || showRemainingDeck) && (
            <span className={styles.deckLabel}>КОЛОДА</span>
          )}
        </div>
      )}

      {/* ── Fan (fan phase only) ── */}
      {phase === 'fan' && fanCards.filter((c) => !c.gone).length > 0 && (
        <FanOfCards
          cards={fanCards}
          onPick={handleFanPick}
          renderCard={() => <TarotCardBack />}
        />
      )}

      {/* ── Flying card ── */}
      {flyCard && (
        <div
          className={styles.flyingCard}
          style={
            {
              left: flyCard.left,
              top: flyCard.top,
              width: FAN_CARD_W,
              height: FAN_CARD_H,
              '--dx': `${flyCard.dx}px`,
              '--dy': `${flyCard.dy}px`,
              '--start-rot': `${flyCard.startRot}deg`,
              '--final-scale': `${FLY_TO_SLOT_SCALE * scale}`,
            } as React.CSSProperties
          }
          onAnimationEnd={handleFlyEnd}
        >
          <TarotCardBack />
        </div>
      )}

      {/* ── Reading-phase tap-anywhere overlay ── */}
      {phase === 'reading' && !isAllRevealed && (
        <div className={styles.revealOverlay} onClick={handleStartReveal} />
      )}

      {/* ── Completion banner ── */}
      {phase === 'complete' && !selected && (
        <div className={styles.completeBanner}>
          ✦ Расклад завершён ✦
        </div>
      )}

      {/* ── LLM narrative reading (complete phase) ── */}
      {phase === 'complete' && (
        <SpreadReading
          spreadType="celtic_cross"
          readingId={readingId}
          cards={cards}
        />
      )}

    </div>
  )
}
