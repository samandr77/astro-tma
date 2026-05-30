import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { FanOfCards, type FanCard } from './FanOfCards'
import { FlipCard } from './FlipCard'
import { TarotCardBack } from './TarotCardBack'
import { useHaptic } from '@/hooks/useTelegram'
import type { TarotCardDetail } from '@/types'
import { CARD_H, CARD_W, SPREAD_CONFIG, type SpreadKey } from '@/data/spread-config'
import styles from './CelticCrossFlow.module.css'

const INITIAL_FAN_COUNT = 15

type DrawSpreadKey = Exclude<SpreadKey, 'celtic_cross'>
type Phase = 'idle' | 'shuffle' | 'fan' | 'reading' | 'complete'

interface FlyCardState {
  left: number
  top: number
  dx: number
  dy: number
  startRot: number
  targetIdx: number
}

interface Props {
  spreadType: DrawSpreadKey
  cards: TarotCardDetail[]
  reusedExisting?: boolean
  nextResetAt?: string | null
  onAllFlipped?: () => void
}

function formatReset(value?: string | null) {
  if (!value) return null
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Europe/Minsk',
  }).format(new Date(value))
}

export function DrawSpreadFlow({
  spreadType,
  cards,
  reusedExisting = false,
  nextResetAt,
  onAllFlipped,
}: Props) {
  const { impact } = useHaptic()
  const config = SPREAD_CONFIG[spreadType]
  const slots = config.layout.slots.map((slot, idx) => ({
    ...slot,
    slot: idx + 1,
    symbol: config.previewSymbols?.[idx] ?? String(idx + 1),
  }))
  const layoutW = config.layout.w
  const layoutH = config.layout.h
  const resetLabel = formatReset(nextResetAt)

  const [phase, setPhase] = useState<Phase>(reusedExisting ? 'complete' : 'idle')
  const [fanCards, setFanCards] = useState<FanCard[]>([])
  const [placed, setPlaced] = useState<Set<number>>(
    () => new Set(reusedExisting ? cards.map((_, idx) => idx) : []),
  )
  const [flyCard, setFlyCard] = useState<FlyCardState | null>(null)
  const [revealedCount, setRevealedCount] = useState(
    reusedExisting ? cards.length : 0,
  )
  const [isAutoRevealing, setIsAutoRevealing] = useState(false)
  const [scale, setScale] = useState(1)

  const areaRef = useRef<HTMLDivElement>(null)
  const slotRefs = useRef<Map<number, HTMLDivElement>>(new Map())

  const placedCount = placed.size
  const isAllPlaced = placedCount >= cards.length
  const isAllRevealed = revealedCount >= cards.length

  useEffect(() => {
    const el = areaRef.current
    if (!el) return

    const update = () => {
      const avail = el.clientWidth
      if (!avail) return
      setScale(Math.min(1, avail / layoutW))
    }

    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [layoutW])

  useEffect(() => {
    if (isAllRevealed && cards.length > 0) {
      onAllFlipped?.()
    }
  }, [isAllRevealed, cards.length, onAllFlipped])

  useEffect(() => {
    if (phase === 'fan' && isAllPlaced) {
      const t = setTimeout(() => setPhase('reading'), 500)
      return () => clearTimeout(t)
    }
  }, [phase, isAllPlaced])

  useEffect(() => {
    if (!isAutoRevealing || phase !== 'reading') return

    if (isAllRevealed) {
      setIsAutoRevealing(false)
      setPhase('complete')
      return
    }

    const t = setTimeout(
      () => setRevealedCount((count) => Math.min(count + 1, cards.length)),
      revealedCount === 0 ? 120 : 420,
    )

    return () => clearTimeout(t)
  }, [isAutoRevealing, phase, isAllRevealed, revealedCount, cards.length])

  const handleDeckClick = useCallback(() => {
    if (phase !== 'idle') return
    impact('medium')
    setPhase('shuffle')
    setTimeout(() => {
      setFanCards(Array.from({ length: INITIAL_FAN_COUNT }, (_, id) => ({ id })))
      setPhase('fan')
    }, 1200)
  }, [phase, impact])

  const handleFanPick = useCallback(
    (id: number, rect: DOMRect, startRot: number) => {
      if (flyCard || placedCount >= cards.length) return

      const targetEl = slotRefs.current.get(placedCount)
      if (!targetEl) return
      const targetRect = targetEl.getBoundingClientRect()

      impact('light')
      setFanCards((prev) =>
        prev.map((card) => (card.id === id ? { ...card, gone: true } : card)),
      )

      const startCenterX = rect.left + rect.width / 2
      const startCenterY = rect.top + rect.height / 2
      const targetCenterX = targetRect.left + targetRect.width / 2
      const targetCenterY = targetRect.top + targetRect.height / 2

      setFlyCard({
        left: startCenterX - CARD_W / 2,
        top: startCenterY - CARD_H / 2,
        dx: targetCenterX - startCenterX,
        dy: targetCenterY - startCenterY,
        startRot,
        targetIdx: placedCount,
      })
    },
    [flyCard, placedCount, cards.length, impact],
  )

  const handleFlyEnd = useCallback(() => {
    if (!flyCard) return
    const idx = flyCard.targetIdx
    setPlaced((prev) => new Set(prev).add(idx))
    setFlyCard(null)
  }, [flyCard])

  const handleStartReveal = useCallback(() => {
    if (phase !== 'reading') return
    if (isAutoRevealing || isAllRevealed) return
    impact('medium')
    setIsAutoRevealing(true)
  }, [phase, isAutoRevealing, isAllRevealed, impact])

  const prompt =
    reusedExisting && phase === 'complete'
      ? resetLabel
        ? `Расклад активен до ${resetLabel}`
        : 'Расклад активен'
      : phase === 'idle'
        ? `Вытяните ${cards.length} карт`
        : phase === 'shuffle'
          ? 'Карты перемешиваются...'
          : phase === 'fan'
            ? `Выбрано ${placedCount} из ${cards.length}`
            : phase === 'reading'
              ? isAutoRevealing
                ? 'Карты открываются...'
                : 'Нажмите один раз, чтобы открыть карты'
              : 'Расклад открыт'

  const containerPadded = phase === 'idle' || phase === 'shuffle' || phase === 'fan'
  const isRevealCta =
    phase === 'reading' && !isAllRevealed && !isAutoRevealing
  const showRemainingDeck = phase === 'reading' || phase === 'complete'

  return (
    <div className={`${styles.flowContainer} ${containerPadded ? '' : styles.noPad}`}>
      {!isRevealCta && (
        <p className={styles.prompt} style={{ minHeight: 20 }}>
          {prompt}
        </p>
      )}

      <div className={styles.spreadArea} ref={areaRef}>
        <div
          className={styles.spreadFit}
          style={{ width: layoutW * scale, height: layoutH * scale }}
        >
          <div
            className={styles.spreadContainer}
            style={{
              width: layoutW,
              height: layoutH,
              transform: `scale(${scale})`,
            }}
          >
            {slots.map((slot, idx) => {
              const card = cards[idx]
              const isPlaced = placed.has(idx)
              const isRevealed = idx < revealedCount
              const isCross = !!slot.rotate

              return (
                <div
                  key={slot.slot}
                  className={`${styles.slot} ${isCross ? styles.slotCross : ''}`}
                  ref={(el) => {
                    if (el) slotRefs.current.set(idx, el)
                    else slotRefs.current.delete(idx)
                  }}
                  style={{
                    left: slot.x,
                    top: slot.y,
                    width: CARD_W,
                    height: CARD_H,
                  }}
                >
                  <div
                    className={styles.rotor}
                    style={
                      isCross
                        ? { transform: `rotate(${slot.rotate}deg)` }
                        : undefined
                    }
                  >
                    {!isPlaced || !card ? (
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
                      <FlipCard
                        revealed={isRevealed}
                        width={CARD_W}
                        height={CARD_H}
                        back={<TarotCardBack />}
                        front={
                          card.image_url ? (
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
                              loading="lazy"
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
                              {card.emoji}
                            </div>
                          )
                        }
                      />
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

      {phase === 'fan' && fanCards.filter((card) => !card.gone).length > 0 && (
        <FanOfCards
          cards={fanCards}
          onPick={handleFanPick}
          renderCard={() => <TarotCardBack />}
        />
      )}

      {flyCard && (
        <div
          className={styles.flyingCard}
          style={
            {
              left: flyCard.left,
              top: flyCard.top,
              width: CARD_W,
              height: CARD_H,
              '--dx': `${flyCard.dx}px`,
              '--dy': `${flyCard.dy}px`,
              '--start-rot': `${flyCard.startRot}deg`,
              '--final-scale': `${scale}`,
            } as CSSProperties
          }
          onAnimationEnd={handleFlyEnd}
        >
          <TarotCardBack />
        </div>
      )}

      {phase === 'reading' && !isAllRevealed && (
        <div className={styles.revealOverlay} onClick={handleStartReveal} />
      )}
    </div>
  )
}
