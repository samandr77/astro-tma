import { useState, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import WebApp from "@twa-dev/sdk";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { HeaderAvatarButton } from "@/components/ui/HeaderAvatarButton";
import { SpreadIntro } from "./SpreadIntro";
import { CelticCrossFlow } from "@/components/tarot/CelticCrossFlow";
import { DrawSpreadFlow } from "@/components/tarot/DrawSpreadFlow";
import { SpreadReading } from "@/components/tarot/SpreadReading";
import { TarotHistory } from "@/components/tarot/TarotHistory";
import { ApiError, tarotApi } from "@/services/api";
import { useAppStore } from "@/stores/app";
import { useHaptic } from "@/hooks/useTelegram";
import { useTelegramBackButton } from "@/hooks/useTelegram";
import type { TarotSpreadResponse } from "@/types";
import type { SpreadKey } from "@/data/spread-config";

type SpreadType = SpreadKey;

interface SpreadOption {
  id: SpreadType;
  name: string;
  cardCount: number;
}

const SPREADS: SpreadOption[] = [
  { id: "three_card",   name: "Прошлое · Настоящее · Будущее", cardCount: 3 },
  { id: "celtic_cross", name: "Кельтский Крест",               cardCount: 10 },
  { id: "week",         name: "Карты на неделю",               cardCount: 7 },
  { id: "relationship", name: "Отношения",                     cardCount: 5 },
];

export function Tarot() {
  const { setScreen } = useAppStore();
  const { impact } = useHaptic();
  const [selectedSpread, setSelectedSpread] = useState<SpreadType | null>(null);
  const [reading, setReading] = useState<TarotSpreadResponse | null>(null);
  const [showInfo, setShowInfo] = useState(true);
  const [allFlipped, setAllFlipped] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  const drawMutation = useMutation({
    mutationFn: tarotApi.draw,
    onSuccess: (data) => {
      impact("success" as any);
      setReading(data);
      setAllFlipped(false);
    },
  });

  const handleBack = useCallback(() => {
    if (reading) {
      setReading(null);
      setAllFlipped(false);
      setSelectedSpread(null);
      setShowInfo(true);
      drawMutation.reset();
    } else if (!showInfo && selectedSpread) {
      setShowInfo(true);
    } else if (selectedSpread) {
      setSelectedSpread(null);
      setShowInfo(true);
    } else if (showHistory) {
      setShowHistory(false);
    } else {
      setScreen("discover", "back");
    }
  }, [reading, selectedSpread, showInfo, showHistory, setScreen, drawMutation]);

  const isSpreadInProgress = !!reading || drawMutation.isPending;

  const requestBack = useCallback(() => {
    if (!isSpreadInProgress) {
      handleBack();
      return;
    }
    const message =
      "Вы уверены, что хотите выйти?\nТекущий расклад будет потерян.";
    if (WebApp.initData && typeof WebApp.showConfirm === "function") {
      WebApp.showConfirm(message, (confirmed: boolean) => {
        if (confirmed) handleBack();
      });
    } else if (window.confirm(message)) {
      handleBack();
    }
  }, [isSpreadInProgress, handleBack]);

  useTelegramBackButton(requestBack, true);

  const handleSelectSpread = (spread: SpreadOption) => {
    impact("light");
    setSelectedSpread(spread.id);
    setReading(null);
    setAllFlipped(false);
    setShowInfo(true);
    drawMutation.reset();
  };

  const handleDraw = () => {
    if (!selectedSpread) return;
    impact("medium");
    drawMutation.mutate(selectedSpread);
  };

  const handleStartSpread = () => {
    if (!selectedSpread) return;

    setShowInfo(false);
    handleDraw();
  };

  if (!selectedSpread && showHistory) {
    return (
      <div className="screen tarot-screen">
        <div className="screen-header screen-header--with-back">
          <button
            className="back-btn"
            onClick={() => setShowHistory(false)}
            aria-label="Назад"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M13 4l-6 6 6 6" />
            </svg>
          </button>
          <h2 className="screen-title">История раскладов</h2>
        </div>
        <div className="screen-content">
          <TarotHistory />
        </div>
      </div>
    );
  }

  if (!selectedSpread) {
    return (
      <div className="screen tarot-screen">
        <div className="screen-header screen-header--with-back screen-header--with-back-avatar">
          <button
            className="back-btn"
            onClick={() => setScreen("discover", "back")}
            aria-label="Назад"
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M13 4l-6 6 6 6" />
            </svg>
          </button>
          <h2 className="screen-title">Таро</h2>
          <HeaderAvatarButton />
        </div>
        <div className="screen-content">
          {SPREADS.map((spread) => (
            <motion.div
              key={spread.id}
              className="spread-option"
              onClick={() => handleSelectSpread(spread)}
              whileTap={{ scale: 0.97 }}
            >
              <div className="spread-option__info">
                <div className="spread-option__name">{spread.name}</div>
                <div className="spread-option__count">{spread.cardCount} карт</div>
              </div>
            </motion.div>
          ))}

          <motion.div
            className="spread-option"
            onClick={() => {
              impact("light");
              setShowHistory(true);
            }}
            whileTap={{ scale: 0.97 }}
            style={{ marginTop: 8, opacity: 0.9 }}
          >
            <div className="spread-option__info">
              <div className="spread-option__name">📜 История раскладов</div>
              <div className="spread-option__count">
                Ваши прошлые расклады
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    );
  }

  const spreadInfo = SPREADS.find((s) => s.id === selectedSpread)!;
  const showIntro =
    showInfo && !reading && !drawMutation.isPending && !drawMutation.isError;

  if (showIntro) {
    return (
      <div className="screen tarot-screen">
        <div className="screen-header screen-header--with-back">
          <button className="back-btn" onClick={handleBack} aria-label="Назад">
            <svg
              width="20"
              height="20"
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M13 4l-6 6 6 6" />
            </svg>
          </button>
        </div>
        <div className="screen-content">
          <SpreadIntro
            spreadKey={selectedSpread}
            onStart={handleStartSpread}
          />
        </div>
      </div>
    );
  }

  return (
    <div className="screen tarot-screen">
      <div className="screen-header screen-header--with-back">
        <button className="back-btn" onClick={handleBack} aria-label="Назад">
          <svg
            width="20"
            height="20"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M13 4l-6 6 6 6" />
          </svg>
        </button>
        <h2 className="screen-title">{spreadInfo.name}</h2>
      </div>

      <div className="screen-content">
        {drawMutation.isPending && (
          <LoadingSpinner message="Тасуем колоду..." />
        )}

        {drawMutation.isError && (() => {
          const err = drawMutation.error;
          const isRateLimit = err instanceof ApiError && err.status === 429;
          const message = isRateLimit && err instanceof ApiError
            ? err.message
            : "Не удалось загрузить расклад. Попробуйте ещё раз.";
          return (
            <div className="error-state">
              <svg
                width="32"
                height="32"
                viewBox="0 0 32 32"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity="0.5"
              >
                <circle cx="16" cy="16" r="13" />
                <line x1="16" y1="10" x2="16" y2="17" />
                <circle cx="16" cy="21" r="1" fill="currentColor" stroke="none" />
              </svg>
              <p>{message}</p>
              {!isRateLimit && (
                <button
                  className="btn-ghost"
                  onClick={() => {
                    drawMutation.reset();
                    handleDraw();
                  }}
                >
                  Повторить
                </button>
              )}
            </div>
          );
        })()}

        {reading && selectedSpread === "celtic_cross" && (
          <CelticCrossFlow
            readingId={reading.reading_id}
            cards={reading.cards}
          />
        )}

        {reading &&
          selectedSpread !== "celtic_cross" && (
            <>
              <DrawSpreadFlow
                spreadType={selectedSpread}
                cards={reading.cards}
                nextResetAt={reading.next_reset_at}
                onAllFlipped={() => setAllFlipped(true)}
              />
              {allFlipped && (
                <SpreadReading
                  spreadType={selectedSpread}
                  readingId={reading.reading_id}
                  cards={reading.cards}
                />
              )}
            </>
          )}
      </div>
    </div>
  );
}
