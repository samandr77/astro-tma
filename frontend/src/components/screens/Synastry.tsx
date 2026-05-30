import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { PremiumGate } from "@/components/ui/PremiumGate";
import {
  CityAutocomplete,
  type CityOption,
} from "@/components/ui/CityAutocomplete";
import { useAppStore } from "@/stores/app";
import { synastryApi, ApiError } from "@/services/api";
import { useHaptic } from "@/hooks/useTelegram";
import { SynastryReport } from "@/components/synastry/SynastryReport";
import type {
  SynastryHistoryItem,
  SynastryResult,
  SynastryManualInput,
} from "@/types";

type Mode = "pick" | "invite" | "manual";

const MIN_SYNASTRY_AGE = 14;

const TELEGRAM_BOT_USERNAME = (
  (import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string | undefined) ??
  "astrologiyatut_bot"
)
  .trim()
  .replace(/^@/, "");

const INVALID_INVITE_BOT_USERNAMES = new Set([
  "astro_bot",
  "bot_username",
  "your_bot_username",
  "telegram_bot_username",
]);

function normalizeSynastryInviteUrl(url: string): string {
  if (!TELEGRAM_BOT_USERNAME) return url;

  try {
    const parsed = new URL(url);
    const isTelegramHost =
      parsed.hostname === "t.me" || parsed.hostname === "telegram.me";
    const parts = parsed.pathname.split("/").filter(Boolean);
    const botUsername = parts[0]?.toLowerCase();

    if (
      isTelegramHost &&
      botUsername &&
      INVALID_INVITE_BOT_USERNAMES.has(botUsername)
    ) {
      parts[0] = TELEGRAM_BOT_USERNAME;
      parsed.pathname = `/${parts.join("/")}`;
      return parsed.toString();
    }
  } catch {
    return url;
  }

  return url;
}

function normalizeBirthDateInput(value: string): string | null {
  const trimmed = value.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return trimmed;

  const match = trimmed.match(/^(\d{1,2})[./](\d{1,2})[./](\d{4})$/);
  if (!match) return null;

  const [, day, month, year] = match;
  const dd = day.padStart(2, "0");
  const mm = month.padStart(2, "0");
  const normalized = `${year}-${mm}-${dd}`;
  const parsed = new Date(Date.UTC(Number(year), Number(mm) - 1, Number(dd)));

  if (
    Number.isNaN(parsed.getTime()) ||
    parsed.getUTCFullYear() !== Number(year) ||
    parsed.getUTCMonth() + 1 !== Number(mm) ||
    parsed.getUTCDate() !== Number(dd)
  ) {
    return null;
  }

  return normalized;
}

function formatBirthDateInput(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 8);
  if (digits.length <= 2) return digits;
  if (digits.length <= 4) return `${digits.slice(0, 2)}.${digits.slice(2)}`;
  return `${digits.slice(0, 2)}.${digits.slice(2, 4)}.${digits.slice(4)}`;
}

function isBirthDateAtLeastAge(isoDate: string, minAge: number): boolean {
  const [year, month, day] = isoDate.split("-").map(Number);
  const birthDate = new Date(year, month - 1, day);
  const cutoff = new Date();
  cutoff.setFullYear(cutoff.getFullYear() - minAge);
  cutoff.setHours(0, 0, 0, 0);
  return birthDate <= cutoff;
}

function validatePartnerBirthDate(value: string): {
  normalizedDate: string | null;
  message: string | null;
} {
  const normalizedDate = normalizeBirthDateInput(value);
  if (!normalizedDate) {
    return {
      normalizedDate: null,
      message: "Введите дату рождения в формате ДД.ММ.ГГГГ.",
    };
  }

  if (!isBirthDateAtLeastAge(normalizedDate, MIN_SYNASTRY_AGE)) {
    return {
      normalizedDate: null,
      message: `Партнёру должно быть не меньше ${MIN_SYNASTRY_AGE} лет.`,
    };
  }

  return { normalizedDate, message: null };
}

function getManualSynastryErrorMessage(error: unknown): string | null {
  if (!error) return null;

  if (!(error instanceof ApiError)) {
    return "Не удалось отправить запрос. Проверьте соединение и попробуйте ещё раз.";
  }

  if (error.status === 401) {
    return "Сессия Telegram устарела. Закройте и снова откройте приложение.";
  }

  if (error.status === 402) return "Сначала купите Синастрию.";

  if (error.status === 422) {
    return error.message || "Проверьте дату, время и город рождения.";
  }

  if (error.message && error.message !== "Internal server error") {
    return error.message;
  }

  return "Не удалось рассчитать совместимость. Проверьте данные и попробуйте ещё раз.";
}

export function Synastry() {
  const { setScreen } = useAppStore();
  const { impact, notification } = useHaptic();
  const queryClient = useQueryClient();
  const [localResult, setLocalResult] = useState<SynastryResult | null>(null);
  const [mode, setMode] = useState<Mode>("pick");
  const [openingHistoryId, setOpeningHistoryId] = useState<number | null>(null);

  const requestMutation = useMutation({
    mutationFn: synastryApi.createRequest,
    onSuccess: () => notification("success"),
    onError: () => notification("error"),
  });

  const { data: pending } = useQuery({
    queryKey: ["synastry-pending"],
    queryFn: synastryApi.pending,
    staleTime: 60_000,
  });

  const acceptMutation = useMutation({
    mutationFn: (token: string) => synastryApi.accept(token),
    onSuccess: (data) => {
      setLocalResult(data);
      notification("success");
      queryClient.invalidateQueries({ queryKey: ["synastry-history"] });
      queryClient.invalidateQueries({ queryKey: ["synastry-pending"] });
    },
    onError: (err) => {
      notification("error");
      if (err instanceof Error && window.alert) window.alert(err.message);
    },
  });

  const openHistoryMutation = useMutation({
    mutationFn: (id: number) => synastryApi.result(id),
    onSuccess: (data) => {
      setLocalResult(data);
      setOpeningHistoryId(null);
    },
    onError: () => {
      setOpeningHistoryId(null);
      notification("error");
    },
  });

  const invite = requestMutation.data;
  const inviteUrl = invite ? normalizeSynastryInviteUrl(invite.invite_url) : "";
  const result = localResult;

  const copy = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => {
      impact("light");
    });
  };

  return (
    <div className="screen synastry-screen">
      <div className="screen-header screen-header--with-back">
        <button
          className="back-btn"
          onClick={() => {
            if (mode !== "pick" && !result) {
              setMode("pick");
              return;
            }
            setScreen("discover", "back");
          }}
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
        <h2 className="screen-title">Синастрия</h2>
      </div>

      <div className="screen-content">
        {result ? (
          <SynastryResultView
            result={result}
            onReset={() => {
              setLocalResult(null);
              setMode("pick");
            }}
          />
        ) : (
          <PremiumGate
            productId="synastry"
            productName="Синастрия"
            stars={100}
          >
            {pending && pending.length > 0 && (
              <div className="horoscope-card" style={{ marginBottom: 12 }}>
                <div
                  className="horoscope-card__period"
                  style={{ marginBottom: 8 }}
                >
                  Входящие приглашения
                </div>
                {pending.map((p) => (
                  <div
                    key={p.id}
                    className="transit-row"
                    style={{ gridTemplateColumns: "1fr auto" }}
                  >
                    <span>{p.initiator_name} приглашает вас на Синастрию</span>
                    <button
                      className="btn-primary"
                      onClick={() => acceptMutation.mutate(p.token)}
                      disabled={acceptMutation.isPending}
                    >
                      {acceptMutation.isPending ? "..." : "Принять"}
                    </button>
                  </div>
                ))}
              </div>
            )}

            {mode === "pick" && (
              <SynastryHistorySection
                onOpen={(item) => {
                  setOpeningHistoryId(item.id);
                  openHistoryMutation.mutate(item.id);
                }}
              />
            )}

            {mode === "pick" && (
              <div className="synastry-modes">
                <p className="synastry-modes__intro">
                  Синастрия — карта встречи двух натальных гороскопов. Выберите,
                  как добавить партнёра.
                </p>

                <motion.button
                  type="button"
                  className="synastry-mode-card"
                  onClick={() => {
                    impact("light");
                    setMode("invite");
                  }}
                  whileTap={{ scale: 0.97 }}
                >
                  <div className="synastry-mode-card__icon">🔗</div>
                  <div className="synastry-mode-card__body">
                    <div className="synastry-mode-card__title">
                      Пригласить по ссылке
                    </div>
                    <div className="synastry-mode-card__desc">
                      Партнёр получит ссылку, откроет и увидит ваш общий расчёт.
                    </div>
                  </div>
                </motion.button>

                <motion.button
                  type="button"
                  className="synastry-mode-card"
                  onClick={() => {
                    impact("light");
                    setMode("manual");
                  }}
                  whileTap={{ scale: 0.97 }}
                >
                  <div className="synastry-mode-card__icon">✍</div>
                  <div className="synastry-mode-card__body">
                    <div className="synastry-mode-card__title">
                      Ввести данные партнёра
                    </div>
                    <div className="synastry-mode-card__desc">
                      Если партнёр не в Telegram — укажите дату, время и город
                      его рождения.
                    </div>
                  </div>
                </motion.button>
              </div>
            )}

            {mode === "invite" && (
              <div className="horoscope-card">
                <div
                  className="horoscope-card__period"
                  style={{ marginBottom: 8 }}
                >
                  Приглашение партнёра
                </div>
                <p
                  style={{
                    color: "var(--text-dim)",
                    fontSize: 13,
                    marginBottom: 16,
                  }}
                >
                  Создайте ссылку-приглашение и отправьте партнёру. После того
                  как он её откроет, оба увидите карту отношений: топ аспектов и
                  пять сфер совместимости.
                </p>
                {!invite ? (
                  <button
                    className="btn-primary"
                    onClick={() => requestMutation.mutate()}
                    disabled={requestMutation.isPending}
                  >
                    {requestMutation.isPending
                      ? "Создаём..."
                      : "Создать приглашение"}
                  </button>
                ) : (
                  <>
                    <p
                      style={{
                        fontSize: 12,
                        color: "var(--text-dim)",
                        marginBottom: 6,
                      }}
                    >
                      Ссылка-приглашение (действительна 7 дней):
                    </p>
                    <div
                      onClick={() => copy(inviteUrl)}
                      style={{
                        padding: "10px 12px",
                        background: "rgba(255,255,255,0.04)",
                        borderRadius: 10,
                        fontSize: 12,
                        fontFamily: "monospace",
                        wordBreak: "break-all",
                        cursor: "pointer",
                        marginBottom: 12,
                      }}
                    >
                      {inviteUrl}
                    </div>
                    <button
                      className="btn-primary"
                      onClick={() => {
                        const tg = (window as any).Telegram?.WebApp;
                        tg?.openTelegramLink?.(
                          `https://t.me/share/url?url=${encodeURIComponent(inviteUrl)}&text=${encodeURIComponent("Давай узнаем нашу совместимость!")}`,
                        );
                      }}
                    >
                      Поделиться в Telegram
                    </button>
                  </>
                )}
                {requestMutation.error instanceof ApiError && (
                  <p style={{ color: "#e88b8b", fontSize: 12, marginTop: 8 }}>
                    {requestMutation.error.status === 422
                      ? "Заполните данные рождения в профиле."
                      : requestMutation.error.status === 402
                        ? "Сначала купите Синастрию."
                        : requestMutation.error.status === 500
                          ? requestMutation.error.message
                          : "Не удалось создать приглашение."}
                  </p>
                )}
              </div>
            )}

            {mode === "manual" && (
              <ManualPartnerForm
                onResult={(r) => {
                  setLocalResult(r);
                  queryClient.invalidateQueries({
                    queryKey: ["synastry-history"],
                  });
                }}
              />
            )}

            {openingHistoryId !== null && (
              <p
                style={{
                  textAlign: "center",
                  marginTop: 8,
                  color: "var(--text-dim)",
                  fontSize: 12,
                }}
              >
                Загружаем расклад…
              </p>
            )}
          </PremiumGate>
        )}
      </div>
    </div>
  );
}

function ManualPartnerForm({
  onResult,
}: {
  onResult: (r: SynastryResult) => void;
}) {
  const [name, setName] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("12:00");
  const [timeKnown, setTimeKnown] = useState(true);
  const [city, setCity] = useState("");
  const [coords, setCoords] = useState<CityOption | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  const manualMutation = useMutation({
    mutationFn: (payload: SynastryManualInput) => synastryApi.manual(payload),
    onSuccess: (result) => onResult(result),
    onError: (err) => {
      const msg = err instanceof Error ? err.message : "Не удалось рассчитать";
      setLocalError(msg);
    },
  });

  const canSubmit =
    name.trim().length > 0 &&
    date.trim().length > 0 &&
    city.trim().length > 0 &&
    !manualMutation.isPending;

  const submit = () => {
    if (!canSubmit) return;

    const dateValidation = validatePartnerBirthDate(date);
    if (!dateValidation.normalizedDate) {
      setLocalError(dateValidation.message);
      return;
    }

    setLocalError(null);
    manualMutation.mutate({
      partner_name: name.trim(),
      birth_date: dateValidation.normalizedDate,
      birth_time: time,
      birth_time_known: timeKnown,
      birth_city: coords?.cityName ?? city.trim(),
      birth_lat: coords?.lat,
      birth_lng: coords?.lng,
      birth_tz: "", // backend resolves from lat/lng or city
    });
  };

  const errMsg =
    localError ?? getManualSynastryErrorMessage(manualMutation.error);

  return (
    <div className="horoscope-card">
      <div className="horoscope-card__period" style={{ marginBottom: 8 }}>
        Данные партнёра
      </div>
      <p
        style={{
          color: "var(--text-dim)",
          fontSize: 13,
          marginBottom: 16,
        }}
      >
        Укажите дату, время и город рождения партнёра. Часовой пояс определим
        автоматически.
      </p>
      <label className="form-label">
        Имя партнёра
        <input
          className="form-input"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Например, Анна"
        />
      </label>
      <label className="form-label">
        Дата рождения
        <input
          className="form-input"
          type="text"
          inputMode="numeric"
          value={date}
          onChange={(e) => {
            setDate(formatBirthDateInput(e.target.value));
            setLocalError(null);
            manualMutation.reset();
          }}
          placeholder="ДД.ММ.ГГГГ"
          autoComplete="bday"
          maxLength={10}
        />
      </label>
      <label className="form-label">
        Время рождения
        <input
          className="form-input"
          type="time"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          disabled={!timeKnown}
        />
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginTop: 6,
            fontSize: 12,
            color: "var(--text-muted)",
          }}
        >
          <input
            type="checkbox"
            checked={!timeKnown}
            onChange={(e) => setTimeKnown(!e.target.checked)}
          />
          Время неизвестно (используем 12:00)
        </label>
      </label>
      <label className="form-label">
        Город рождения
        <CityAutocomplete
          value={city}
          onChange={(v) => {
            setCity(v);
            if (coords && v !== coords.displayName) setCoords(null);
          }}
          onSelect={(opt) => {
            setCity(opt.displayName);
            setCoords(opt);
          }}
          placeholder="Москва, Лондон, Нью-Йорк..."
        />
      </label>

      <button
        className="btn-primary"
        style={{ marginTop: 8 }}
        disabled={!canSubmit}
        onClick={submit}
      >
        {manualMutation.isPending ? "Считаем..." : "Рассчитать совместимость"}
      </button>

      {errMsg && (
        <p style={{ color: "#e88b8b", fontSize: 12, marginTop: 8 }}>{errMsg}</p>
      )}
    </div>
  );
}

function SynastryResultView({
  result,
  onReset,
}: {
  result: SynastryResult;
  onReset: () => void;
}) {
  return (
    <>
      <SynastryReport result={result} />

      <button
        className="btn-primary"
        style={{ marginTop: 12 }}
        onClick={onReset}
      >
        Назад к приглашениям
      </button>
    </>
  );
}

function SynastryHistorySection({
  onOpen,
}: {
  onOpen: (item: SynastryHistoryItem) => void;
}) {
  const queryClient = useQueryClient();
  const { impact, notification } = useHaptic();
  const { data, isPending } = useQuery({
    queryKey: ["synastry-history"],
    queryFn: synastryApi.history,
    staleTime: 30_000,
  });

  const hideMutation = useMutation({
    mutationFn: (id: number) => synastryApi.hideHistoryItem(id),
    onSuccess: () => {
      notification("success");
      queryClient.invalidateQueries({ queryKey: ["synastry-history"] });
    },
    onError: () => notification("error"),
  });

  if (isPending) {
    return (
      <div className="horoscope-card" style={{ marginBottom: 12 }}>
        <div className="horoscope-card__period" style={{ marginBottom: 8 }}>
          История раскладов
        </div>
        <p
          style={{
            margin: 0,
            color: "var(--text-dim)",
            fontSize: 13,
            textAlign: "center",
            padding: "8px 0",
          }}
        >
          Загружаем…
        </p>
      </div>
    );
  }
  if (!data || data.length === 0) {
    return (
      <div className="horoscope-card" style={{ marginBottom: 12 }}>
        <div className="horoscope-card__period" style={{ marginBottom: 8 }}>
          История раскладов
        </div>
        <p
          style={{
            margin: 0,
            color: "var(--text-dim)",
            fontSize: 13,
            lineHeight: 1.5,
            textAlign: "center",
            padding: "8px 4px",
          }}
        >
          Здесь появятся прошлые расклады, как только партнёр примет ваше
          приглашение или вы примете чужое.
        </p>
      </div>
    );
  }

  return (
    <div className="horoscope-card" style={{ marginBottom: 12 }}>
      <div className="horoscope-card__period" style={{ marginBottom: 8 }}>
        История раскладов
      </div>
      {data.map((item) => (
        <div
          key={item.id}
          className="syn-history-row"
          onClick={() => {
            impact("light");
            onOpen(item);
          }}
          role="button"
          tabIndex={0}
        >
          <div className="syn-history-row__main">
            <div className="syn-history-row__name">
              {item.partner_name ?? "—"}
            </div>
            <div className="syn-history-row__meta">
              {item.is_initiator ? "Вы пригласили" : "Вас пригласили"} ·{" "}
              {formatHistoryDate(item.created_at)}
            </div>
          </div>
          <div className="syn-history-row__score">{item.scores.overall}%</div>
          <button
            type="button"
            className="syn-history-row__delete"
            aria-label="Удалить"
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm("Удалить расклад из истории?")) {
                hideMutation.mutate(item.id);
              }
            }}
            disabled={hideMutation.isPending}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}

function formatHistoryDate(iso: string): string {
  try {
    const d = new Date(iso);
    return new Intl.DateTimeFormat("ru-RU", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }).format(d);
  } catch {
    return iso;
  }
}
