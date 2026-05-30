import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usersApi, natalApi } from "@/services/api";
import { useAppStore } from "@/stores/app";
import { useHaptic, useTelegramUser } from "@/hooks/useTelegram";
import { ZODIAC_SIGNS } from "@/types";
import {
  CityAutocomplete,
  type CityOption,
} from "@/components/ui/CityAutocomplete";

const MONTHS_RU = [
  "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];

const MONTHS_RU_GENITIVE = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];

function formatBirthDateRu(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const year = m[1];
  const month = parseInt(m[2], 10);
  const day = parseInt(m[3], 10);
  return `${day} ${MONTHS_RU_GENITIVE[month - 1]} ${year}`;
}

/**
 * Day / month / year selects for a birth date — mirrors Onboarding's flow
 * so the year is freely scrollable on iOS (native <input type="date"> only
 * pages through months in Telegram's WebView).
 *
 * `value` and `onChange` use ISO "YYYY-MM-DD"; selects update only when
 * the user picks something, so partial input leaves the others untouched.
 */
function BirthDateInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  const [year, month, day] = useMemo(() => {
    if (!value) return ["", "", ""];
    const m = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return ["", "", ""];
    return [m[1], m[2], m[3]];
  }, [value]);

  const currentYear = new Date().getFullYear();
  const years = useMemo(() => {
    const out: number[] = [];
    for (let y = currentYear; y >= currentYear - 120; y -= 1) out.push(y);
    return out;
  }, [currentYear]);

  const daysInMonth = useMemo(() => {
    const y = parseInt(year || String(currentYear), 10);
    const m = parseInt(month || "1", 10);
    if (!m) return 31;
    return new Date(y, m, 0).getDate();
  }, [year, month, currentYear]);

  const emit = (d: string, m: string, y: string) => {
    if (!d || !m || !y) return;
    onChange(`${y}-${m.padStart(2, "0")}-${d.padStart(2, "0")}`);
  };

  return (
    <div className="birth-date-row">
      <select
        className="form-input birth-date-row__select"
        value={day}
        onChange={(e) => emit(e.target.value, month, year)}
        aria-label="День"
      >
        <option value="">День</option>
        {Array.from({ length: daysInMonth }, (_, i) => i + 1).map((d) => (
          <option key={d} value={String(d).padStart(2, "0")}>
            {d}
          </option>
        ))}
      </select>
      <select
        className="form-input birth-date-row__select"
        value={month}
        onChange={(e) => emit(day, e.target.value, year)}
        aria-label="Месяц"
      >
        <option value="">Месяц</option>
        {MONTHS_RU.map((label, idx) => (
          <option
            key={label}
            value={String(idx + 1).padStart(2, "0")}
          >
            {label}
          </option>
        ))}
      </select>
      <select
        className="form-input birth-date-row__select"
        value={year}
        onChange={(e) => emit(day, month, e.target.value)}
        aria-label="Год"
      >
        <option value="">Год</option>
        {years.map((y) => (
          <option key={y} value={String(y)}>
            {y}
          </option>
        ))}
      </select>
    </div>
  );
}

function PurchasesCard() {
  const { setScreen } = useAppStore();
  const { impact } = useHaptic();
  const { data, isLoading } = useQuery({
    queryKey: ["my-purchases"],
    queryFn: usersApi.getPurchases,
    staleTime: 1000 * 60 * 5,
  });

  if (isLoading) return null;
  const purchases = data?.purchases ?? [];
  const active = data?.active_subscription ?? null;
  const totalCount = purchases.length + (active ? 1 : 0);
  if (totalCount === 0) return null;

  const previewLabel = active
    ? "Премиум-подписка активна"
    : `${totalCount} ${
        totalCount === 1
          ? "покупка"
          : totalCount < 5
            ? "покупки"
            : "покупок"
      }`;

  return (
    <motion.button
      type="button"
      className="premium-status-card purchases-card-button"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.11 }}
      onClick={() => {
        impact("light");
        setScreen("purchases");
      }}
    >
      <span className="premium-status-card__star" aria-hidden="true">✦</span>
      <span className="premium-status-card__main">
        <span className="premium-status-card__title">Мои покупки</span>
        <span className="premium-status-card__desc">{previewLabel}</span>
      </span>
      <span className="premium-status-card__arrow" aria-hidden="true">›</span>
    </motion.button>
  );
}

export function Profile() {
  const { user, setUser } = useAppStore();
  const { impact, notification } = useHaptic();
  const tgUser = useTelegramUser();
  const queryClient = useQueryClient();

  const [editing, setEditing] = useState(false);
  const [photoFailed, setPhotoFailed] = useState(false);
  const [birthDate, setBirthDate] = useState("");
  const [birthTime, setBirthTime] = useState("");
  const [birthTimeKnown, setBirthTimeKnown] = useState(
    user?.birth_time_known ?? false,
  );
  const [birthCity, setBirthCity] = useState(user?.birth_city ?? "");
  const [selectedCoords, setSelectedCoords] = useState<{
    lat: number;
    lng: number;
  } | null>(null);
  const [savedCity, setSavedCity] = useState<string | null>(null);
  const [gender, setGender] = useState(user?.gender ?? "");

  const userSign = ZODIAC_SIGNS.find((s) => s.value === user?.sun_sign);

  const { data: natalSummary } = useQuery({
    queryKey: ["natal-summary"],
    queryFn: natalApi.getSummary,
    enabled: !!user?.birth_city,
    staleTime: 1000 * 60 * 10,
  });

  const openEditor = () => {
    impact("light");
    setBirthCity(displayCity ?? "");
    // Pre-fill date/time/gender from current data so the user sees what is
    // already saved instead of empty selectors.
    setBirthDate(natalSummary?.birth_date ?? "");
    setBirthTimeKnown(
      natalSummary?.birth_time_known ?? user?.birth_time_known ?? false,
    );
    setBirthTime(
      natalSummary?.birth_time_known && natalSummary?.birth_time
        ? natalSummary.birth_time
        : "",
    );
    setGender(user?.gender ?? "");
    setSelectedCoords(null);
    setEditing(true);
  };

  const SIGN_RU: Record<string, string> = {
    Aries: "Овен",
    Taurus: "Телец",
    Gemini: "Близнецы",
    Cancer: "Рак",
    Leo: "Лев",
    Virgo: "Дева",
    Libra: "Весы",
    Scorpio: "Скорпион",
    Sagittarius: "Стрелец",
    Capricorn: "Козерог",
    Aquarius: "Водолей",
    Pisces: "Рыбы",
  };

  const birthMutation = useMutation({
    mutationFn: usersApi.setupBirth,
    onSuccess: async (resp: any) => {
      notification("success");
      impact("medium");
      setSavedCity(resp.city_resolved ?? birthCity);
      setEditing(false);
      const updated = await usersApi.upsertMe();
      setUser(updated);
      queryClient.invalidateQueries({ queryKey: ["natal-summary"] });
      queryClient.invalidateQueries({ queryKey: ["natal-full"] });
    },
  });

  const genderMutation = useMutation({
    mutationFn: (g: string) => usersApi.setGender(g),
    onSuccess: async (updated: any) => {
      setUser(updated);
    },
  });

  const pushMutation = useMutation({
    mutationFn: (enabled: boolean) => usersApi.setPushEnabled(enabled),
    onSuccess: (updated: any) => {
      setUser(updated);
      impact("light");
    },
  });

  const handleSave = async () => {
    impact("light");
    if (gender && gender !== user?.gender) {
      await genderMutation.mutateAsync(gender);
    }
    if (birthDate && birthCity) {
      const datetime =
        birthTimeKnown && birthTime
          ? `${birthDate}T${birthTime}:00`
          : `${birthDate}T12:00:00`;
      birthMutation.mutate({
        birth_date: datetime,
        birth_time_known: birthTimeKnown,
        birth_city: birthCity,
        ...(selectedCoords ?? {}),
      });
    } else if (gender && gender !== user?.gender) {
      // Only gender was changed — close editing
      notification("success");
      setEditing(false);
    }
  };

  const displayCity = savedCity ?? user?.birth_city;

  return (
    <div className="screen profile-screen">
      <div className="screen-header">
        <div className="screen-title-ornament" aria-hidden="true">
          <span className="screen-title-ornament__leaf">✧</span>
          <h2 className="screen-title">Профиль</h2>
          <span className="screen-title-ornament__leaf">✧</span>
        </div>
      </div>

      <div className="screen-content">
        {/* User card */}
        <motion.div
          className="profile-card profile-card--ornate"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div
            className={`profile-avatar${tgUser.photoUrl && !photoFailed ? " profile-avatar--photo" : ""}`}
          >
            {tgUser.photoUrl && !photoFailed ? (
              <img
                src={tgUser.photoUrl}
                alt=""
                onError={() => setPhotoFailed(true)}
              />
            ) : (
              (user?.name?.charAt(0)?.toUpperCase() ?? "?")
            )}
          </div>
          <div className="profile-info">
            <div className="profile-name profile-name--script">{user?.name ?? "Пользователь"}</div>
            <div className="profile-meta">
              {user?.gender && (
                <span className="profile-gender">
                  <span className="profile-gender__symbol" aria-hidden="true">
                    {user.gender === "male" ? "♂" : "♀"}
                  </span>
                  {user.gender === "male" ? "Мужской" : "Женский"}
                </span>
              )}
            </div>
            {(natalSummary?.moon_sign || userSign) && (
              <div className="profile-signs-triple profile-signs-triple--chips">
                <span className="sign-chip">
                  <span className="sign-chip__icon">☉</span>
                  {(natalSummary?.sun_sign && SIGN_RU[natalSummary.sun_sign]) ??
                    userSign?.label}
                </span>
                {natalSummary?.moon_sign && (
                  <span className="sign-chip">
                    <span className="sign-chip__icon">☽</span>
                    {SIGN_RU[natalSummary.moon_sign]}
                  </span>
                )}
                {natalSummary?.ascendant_sign && (
                  <span className="sign-chip">
                    <span className="sign-chip__icon">↑</span>
                    {SIGN_RU[natalSummary.ascendant_sign]}
                  </span>
                )}
              </div>
            )}
          </div>
          {!editing && (
            <button
              type="button"
              className="profile-card__edit"
              onClick={openEditor}
              aria-label="Редактировать"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9.5 2.5l2 2-7 7H2.5v-2l7-7z" />
              </svg>
            </button>
          )}
        </motion.div>

        {/* Premium status card — active or upsell */}
        <motion.button
          type="button"
          className={`premium-status-card ${user?.is_premium ? "" : "premium-status-card--upsell"}`}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          onClick={() => {
            impact("light");
            useAppStore.getState().setScreen("premium");
          }}
        >
          <span className="premium-status-card__star" aria-hidden="true">★</span>
          <span className="premium-status-card__main">
            <span className="premium-status-card__title">
              {user?.is_premium ? "Премиум-доступ" : "Открыть Premium"}
            </span>
            <span className="premium-status-card__desc">
              {user?.is_premium
                ? "Активен"
                : "Все интерпретации, прогнозы и Таро · от 199 ⭐ / мес"}
            </span>
          </span>
          <span className="premium-status-card__arrow" aria-hidden="true">›</span>
        </motion.button>

        {/* Birth data section */}
        <motion.div
          className="natal-card"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08 }}
        >
          <div className="natal-card__tag">✦ Данные рождения</div>

          {!editing ? (
            <>
              {displayCity ? (
                <div className="profile-birth-info">
                  <div className="natal-summary-row">
                    <span className="natal-summary-label">
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 14 14"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M7 1C4.79 1 3 2.79 3 5c0 3.25 4 8 4 8s4-4.75 4-8c0-2.21-1.79-4-4-4z" />
                        <circle cx="7" cy="5" r="1.2" />
                      </svg>
                      Город
                    </span>
                    <span className="natal-summary-value">{displayCity}</span>
                  </div>
                  {natalSummary?.birth_date && (
                    <div className="natal-summary-row">
                      <span className="natal-summary-label">
                        <svg
                          width="14"
                          height="14"
                          viewBox="0 0 14 14"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.4"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <rect x="2" y="3" width="10" height="9" rx="1.5" />
                          <path d="M2 6h10M5 1.5v2M9 1.5v2" />
                        </svg>
                        Дата
                      </span>
                      <span className="natal-summary-value">
                        {formatBirthDateRu(natalSummary.birth_date)}
                      </span>
                    </div>
                  )}
                  <div className="natal-summary-row">
                    <span className="natal-summary-label">
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 14 14"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.4"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <circle cx="7" cy="7" r="5.5" />
                        <polyline points="7,4 7,7 9,8" />
                      </svg>
                      Время
                    </span>
                    <span className="natal-summary-value">
                      {user?.birth_time_known && natalSummary?.birth_time
                        ? natalSummary.birth_time
                        : "Неизвестно (взяли полдень)"}
                    </span>
                  </div>
                </div>
              ) : (
                <p className="profile-birth-empty">
                  Данные рождения не указаны. Добавьте их для расчёта натальной
                  карты.
                </p>
              )}
              <button
                className="btn-primary"
                style={{ marginTop: "0.75rem" }}
                onClick={openEditor}
              >
                {displayCity ? "Изменить" : "Добавить данные"}
              </button>
            </>
          ) : (
            <div className="profile-edit-form">
              <div className="form-group">
                <label className="form-label">Пол</label>
                <div className="gender-toggle">
                  <button
                    type="button"
                    className={`gender-btn${gender === "male" ? " active" : ""}`}
                    onClick={() => setGender("male")}
                  >
                    Мужской
                  </button>
                  <button
                    type="button"
                    className={`gender-btn${gender === "female" ? " active" : ""}`}
                    onClick={() => setGender("female")}
                  >
                    Женский
                  </button>
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Дата рождения</label>
                <BirthDateInput value={birthDate} onChange={setBirthDate} />
              </div>

              <div className="form-group">
                <button
                  type="button"
                  className="toggle-row"
                  onClick={() => setBirthTimeKnown((v) => !v)}
                  aria-pressed={birthTimeKnown}
                >
                  <span className="toggle-row__label">
                    Знаю точное время рождения
                  </span>
                  <span
                    className={`toggle-switch${birthTimeKnown ? " toggle-switch--on" : ""}`}
                  >
                    <span className="toggle-switch__thumb" />
                  </span>
                </button>
              </div>

              {birthTimeKnown && (
                <div className="form-group">
                  <label className="form-label">Время рождения</label>
                  <input
                    type="time"
                    className="form-input"
                    value={birthTime}
                    onChange={(e) => setBirthTime(e.target.value)}
                  />
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Город рождения</label>
                <CityAutocomplete
                  value={birthCity}
                  onChange={(v) => {
                    setBirthCity(v);
                    setSelectedCoords(null);
                  }}
                  onSelect={(opt: CityOption) => {
                    setBirthCity(opt.displayName);
                    setSelectedCoords({ lat: opt.lat, lng: opt.lng });
                  }}
                />
                {selectedCoords && (
                  <div className="city-autocomplete__confirmed">
                    ✓ {selectedCoords.lat.toFixed(4)}°{" "}
                    {selectedCoords.lat >= 0 ? "с.ш." : "ю.ш."}
                    &nbsp;&nbsp;{selectedCoords.lng.toFixed(4)}°{" "}
                    {selectedCoords.lng >= 0 ? "в.д." : "з.д."}
                  </div>
                )}
              </div>

              <div className="profile-edit-actions">
                <motion.button
                  className="btn-primary"
                  onClick={handleSave}
                  disabled={
                    (!gender && !birthDate) ||
                    (birthDate && !birthCity) ||
                    birthMutation.isPending ||
                    genderMutation.isPending
                  }
                  whileTap={{ scale: 0.97 }}
                >
                  {birthMutation.isPending ? "Считаем карту..." : "Сохранить"}
                </motion.button>
                <button
                  className="btn-ghost"
                  onClick={() => {
                    impact("light");
                    setEditing(false);
                  }}
                  disabled={birthMutation.isPending}
                >
                  Отмена
                </button>
              </div>

              {birthMutation.isError && (
                <p className="profile-error">
                  Ошибка сохранения. Проверьте название города.
                </p>
              )}
            </div>
          )}
        </motion.div>

        <PurchasesCard />

        <motion.button
          type="button"
          className="profile-cta-card"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.115 }}
          onClick={() => {
            impact("light");
            useAppStore.getState().setScreen("referral");
          }}
        >
          <span className="profile-cta-card__icon" aria-hidden="true">✦</span>
          <span className="profile-cta-card__col">
            <span className="profile-cta-card__title">Пригласить друзей</span>
            <span className="profile-cta-card__desc">
              Когда друг купит — получите 14 дней Premium
            </span>
          </span>
          <span className="profile-cta-card__chev" aria-hidden="true">›</span>
        </motion.button>

        <motion.div
          className="natal-card"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
        >
          <div className="natal-card__tag">✦ Уведомления</div>
          <div className="push-toggle-row">
            <div>
              <div className="push-toggle-title">Утренний гороскоп</div>
              <div className="push-toggle-desc">
                Сообщение от бота каждое утро ~9:00 по вашему времени
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={user?.push_enabled ?? false}
              className={`push-switch${user?.push_enabled ? " push-switch--on" : ""}`}
              onClick={() =>
                pushMutation.mutate(!(user?.push_enabled ?? false))
              }
              disabled={pushMutation.isPending}
            >
              <span className="push-switch__dot" />
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
