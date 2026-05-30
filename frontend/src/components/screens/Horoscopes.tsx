import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { useState } from "react";
import { EnergyBars } from "@/components/ui/EnergyBars";
import { HoroscopeSkeleton } from "@/components/ui/Skeleton";
import { HeaderAvatarButton } from "@/components/ui/HeaderAvatarButton";
import { horoscopeApi } from "@/services/api";
import { useAppStore } from "@/stores/app";
import { useHaptic } from "@/hooks/useTelegram";
import { ZODIAC_SIGNS, type ZodiacSign } from "@/types";
import { ZodiacIcon } from "@/components/ui/ZodiacIcon";

type Period = "today" | "tomorrow" | "week" | "month";

const PERIOD_LABELS: Record<Period, string> = {
  today: "Сегодня",
  tomorrow: "Завтра",
  week: "Неделя",
  month: "Месяц",
};

/**
 * Horoscopes screen — full grid of zodiac signs at the top, full
 * horoscope text + energy bars below. Lets the user browse the
 * forecast for any sign, not only their own.
 */
export function Horoscopes() {
  const { user } = useAppStore();
  const { impact } = useHaptic();
  const [period, setPeriod] = useState<Period>("today");
  const [selectedSign, setSelectedSign] = useState<ZodiacSign>(
    (user?.sun_sign as ZodiacSign | undefined) ?? "leo",
  );
  const signInfo = ZODIAC_SIGNS.find((s) => s.value === selectedSign);

  const { data: horoscope, isLoading } = useQuery({
    queryKey: ["horoscope-page", period, selectedSign, user?.id],
    queryFn: () =>
      period === "today"
        ? horoscopeApi.getToday(selectedSign)
        : horoscopeApi.getPeriod(period, selectedSign),
    staleTime: 1000 * 60 * 30,
  });

  return (
    <div className="screen horoscopes-screen">
      {/* Header */}
      <div className="screen-header">
        <div>
          <h1 className="screen-title">Гороскопы</h1>
          <p className="screen-subtitle">Выберите знак и период</p>
        </div>
        <HeaderAvatarButton />
      </div>

      <div className="screen-content">
        {/* Zodiac picker grid */}
        <div className="zodiac-grid">
          {ZODIAC_SIGNS.map((s) => {
            const active = s.value === selectedSign;
            return (
              <button
                key={s.value}
                className={`zodiac-grid__item ${active ? "active" : ""}`}
                onClick={() => {
                  impact("light");
                  setSelectedSign(s.value);
                }}
                aria-pressed={active}
              >
                <span className="zodiac-grid__emoji">
                  <ZodiacIcon sign={s.value} size={28} />
                </span>
                <span className="zodiac-grid__label">{s.label}</span>
              </button>
            );
          })}
        </div>

        {/* Period tabs */}
        <div className="period-tabs">
          {(["today", "tomorrow", "week", "month"] as Period[]).map((p) => (
            <button
              key={p}
              className={`period-tab ${period === p ? "active" : ""}`}
              onClick={() => {
                impact("light");
                setPeriod(p);
              }}
            >
              {PERIOD_LABELS[p]}
            </button>
          ))}
        </div>

        {/* Horoscope card */}
        {isLoading ? (
          <HoroscopeSkeleton />
        ) : (
          <motion.div
            key={`horo-${period}-${selectedSign}`}
            className="horoscope-card glass-gold"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="card-tag">✦ {PERIOD_LABELS[period]}</div>
            <div className="card-sign-row">
              <div className="sign-badge">
                {signInfo ? <ZodiacIcon sign={signInfo.value} size={32} /> : "✦"}
              </div>
              <div>
                <div className="sign-name">{signInfo?.label}</div>
                <div className="sign-dates">{signInfo?.dates}</div>
              </div>
            </div>
            <p className="horoscope-text">{horoscope?.text_ru}</p>
            {horoscope?.energy && <EnergyBars scores={horoscope.energy} />}
          </motion.div>
        )}
      </div>
    </div>
  );
}
