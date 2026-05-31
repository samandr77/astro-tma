/**
 * API client — thin wrapper over fetch.
 * Automatically injects X-Init-Data header (Telegram auth).
 * All methods throw on non-2xx — React Query catches them.
 */

import WebApp from "@twa-dev/sdk";

const configuredBaseUrl = (
  (import.meta.env.VITE_API_URL as string | undefined) ?? ""
)
  .trim()
  .replace(/\/+$/, "");
const BASE_URL = configuredBaseUrl
  ? configuredBaseUrl.endsWith("/api")
    ? configuredBaseUrl
    : `${configuredBaseUrl}/api`
  : "/api";

type NatalPdfLinkResponse = {
  download_url: string;
  filename: string;
  expires_in: number;
};

type NatalPdfSendResponse = {
  status: "sent";
  filename: string;
};

type UserProfile = import("@/types").UserProfile;
type NatalSummaryResponse = import("@/types").NatalSummaryResponse;
type NatalFullResponse = import("@/types").NatalFullResponse;
type NatalDescriptionsResponse = import("@/types").NatalDescriptionsResponse;

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function formatApiErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg?: unknown }).msg ?? "");
        }
        return "";
      })
      .filter(Boolean);
    return messages.join("; ") || fallback;
  }

  if (detail && typeof detail === "object" && "msg" in detail) {
    return String((detail as { msg?: unknown }).msg ?? fallback);
  }

  return fallback;
}

function apiUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${BASE_URL}${suffix}`;
}

function openDownloadWindow(): Window | null {
  try {
    const popup = window.open("about:blank", "_blank");
    if (popup?.document) {
      popup.document.title = "Готовим PDF";
      popup.document.body.style.cssText =
        "margin:0;display:grid;place-items:center;min-height:100vh;background:#07060f;color:#f0d48a;font:16px system-ui,sans-serif;";
      popup.document.body.textContent = "Готовим PDF...";
    }
    return popup;
  } catch {
    return null;
  }
}

function triggerDownload(url: string, filename: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  triggerDownload(url, filename);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function canUseTelegramOpenLink(): boolean {
  return Boolean(WebApp.initData) && typeof WebApp.openLink === "function";
}

function shouldUseLocalDevFixtures(): boolean {
  return import.meta.env.DEV && !WebApp.initData;
}

let localDevUser: UserProfile = {
  id: 1,
  name: "Dev User",
  gender: "female",
  sun_sign: "virgo",
  birth_city: "Минск, Беларусь",
  birth_time_known: true,
  push_enabled: true,
  is_premium: true,
  created_at: "2026-01-01T00:00:00Z",
};

const localDevSummary: NatalSummaryResponse = {
  has_chart: true,
  sun_sign: "Virgo",
  moon_sign: "Cancer",
  ascendant_sign: "Pisces",
  mc_sign: "Sagittarius",
  birth_city: "Минск, Беларусь",
  birth_time_known: true,
  birth_lat: 53.9025,
  birth_lng: 27.5618,
  birth_tz: "Europe/Minsk",
  birth_date: "1994-09-12T08:30:00",
  birth_time: "08:30:00",
  planets: {
    sun: {
      degree: 169.4,
      sign_degree: 19.4,
      sign: "Virgo",
      house: 7,
      retrograde: false,
    },
    moon: {
      degree: 104.8,
      sign_degree: 14.8,
      sign: "Cancer",
      house: 5,
      retrograde: false,
    },
    mercury: {
      degree: 172.2,
      sign_degree: 22.2,
      sign: "Virgo",
      house: 7,
      retrograde: false,
    },
    venus: {
      degree: 183.9,
      sign_degree: 3.9,
      sign: "Libra",
      house: 7,
      retrograde: false,
    },
    mars: {
      degree: 221.3,
      sign_degree: 11.3,
      sign: "Scorpio",
      house: 8,
      retrograde: false,
    },
    jupiter: {
      degree: 212.7,
      sign_degree: 2.7,
      sign: "Scorpio",
      house: 8,
      retrograde: true,
    },
    saturn: {
      degree: 199.5,
      sign_degree: 19.5,
      sign: "Libra",
      house: 8,
      retrograde: false,
    },
    uranus: {
      degree: 241.2,
      sign_degree: 1.2,
      sign: "Sagittarius",
      house: 9,
      retrograde: true,
    },
    neptune: {
      degree: 264.9,
      sign_degree: 24.9,
      sign: "Sagittarius",
      house: 10,
      retrograde: true,
    },
    pluto: {
      degree: 204.3,
      sign_degree: 24.3,
      sign: "Libra",
      house: 8,
      retrograde: false,
    },
    chiron: {
      degree: 57.8,
      sign_degree: 27.8,
      sign: "Taurus",
      house: 3,
      retrograde: true,
    },
  },
  houses: [
    { number: 1, degree: 336.4, sign: "Pisces" },
    { number: 2, degree: 6.1, sign: "Aries" },
    { number: 3, degree: 36.2, sign: "Taurus" },
    { number: 4, degree: 66.2, sign: "Gemini" },
    { number: 5, degree: 96.3, sign: "Cancer" },
    { number: 6, degree: 126.4, sign: "Leo" },
    { number: 7, degree: 156.4, sign: "Virgo" },
    { number: 8, degree: 186.1, sign: "Libra" },
    { number: 9, degree: 216.2, sign: "Scorpio" },
    { number: 10, degree: 246.2, sign: "Sagittarius" },
    { number: 11, degree: 276.3, sign: "Capricorn" },
    { number: 12, degree: 306.4, sign: "Aquarius" },
  ],
  aspects: [
    { p1: "sun", p2: "jupiter", aspect: "opposition", orb: 3.7 },
    { p1: "sun", p2: "saturn", aspect: "square", orb: 2.1 },
    { p1: "moon", p2: "venus", aspect: "trine", orb: 1.4 },
    { p1: "moon", p2: "mars", aspect: "opposition", orb: 2.8 },
    { p1: "mercury", p2: "saturn", aspect: "trine", orb: 2.7 },
    { p1: "venus", p2: "mars", aspect: "sextile", orb: 1.2 },
    { p1: "mars", p2: "neptune", aspect: "trine", orb: 2.4 },
    { p1: "jupiter", p2: "pluto", aspect: "sextile", orb: 1.6 },
    { p1: "saturn", p2: "uranus", aspect: "square", orb: 3.0 },
  ],
};

const localDevFull: NatalFullResponse = {
  sun_sign: "Virgo",
  moon_sign: "Cancer",
  ascendant_sign: "Pisces",
  planets: Object.fromEntries(
    Object.entries(localDevSummary.planets ?? {}).map(([key, planet]) => [
      key,
      {
        ...planet,
        sign_ru:
          {
            Virgo: "Дева",
            Cancer: "Рак",
            Libra: "Весы",
            Scorpio: "Скорпион",
            Sagittarius: "Стрелец",
            Taurus: "Телец",
          }[planet.sign] ?? planet.sign,
        speed: planet.retrograde ? -0.12 : 1,
      },
    ]),
  ),
  houses: (localDevSummary.houses ?? []).map((house) => ({
    ...house,
    sign_ru:
      {
        Pisces: "Рыбы",
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
      }[house.sign] ?? house.sign,
  })),
  aspects: (localDevSummary.aspects ?? []).map((aspect) => ({
    ...aspect,
    applying: aspect.orb < 2.5,
  })),
  interpretations: [
    {
      planet: "sun",
      category: "personality",
      text: "Солнце в Деве делает фокус на точности, пользе и спокойной собранности. Важные решения легче принимать через практическую проверку, а не через импульс.",
    },
    {
      planet: "moon",
      category: "emotion",
      text: "Луна в Раке усиливает память чувств и потребность в безопасной среде. Эмоциональная устойчивость приходит через близость, дом и понятный ритм.",
    },
    {
      planet: "venus",
      category: "love",
      text: "Венера в Весах ищет взаимность, красоту и честный баланс. В отношениях особенно важны тон, уважение и ощущение равного диалога.",
    },
  ],
  reading:
    "Общий рисунок\nКарта соединяет практичность Девы, эмоциональную глубину Рака и мягкий восходящий знак Рыб. Это сочетание даёт внимательность к деталям, сильную эмпатию и потребность делать полезные вещи красиво.\n\nГлавный вектор\nСильная зона отношений и общих ресурсов показывает, что рост часто приходит через честные союзы, доверие и умение договариваться о границах.",
};

const localDevDescriptions: NatalDescriptionsResponse = {
  planets: Object.fromEntries(
    Object.keys(localDevFull.planets).map((planet) => [
      planet,
      {
        short: "Короткое тестовое описание для локальной проверки карточки.",
        full: "Полное тестовое описание показывает, как будет выглядеть раскрытая карточка в локальном браузере. Текст специально длиннее одной строки, чтобы проверить переносы на телефоне.",
      },
    ]),
  ),
  houses: Object.fromEntries(
    localDevFull.houses.map((house) => [
      String(house.number),
      {
        short: "Дом описывает сферу жизни и её естественный ритм.",
        full: "Тестовое описание дома помогает проверить, что длинный текст не вылезает из карточки и корректно переносится на узком экране.",
      },
    ]),
  ),
  aspects: localDevFull.aspects.map((aspect) => ({
    p1: aspect.p1,
    p2: aspect.p2,
    type: aspect.aspect,
    short: "Аспект показывает динамику между двумя планетами.",
    full: "Длинное описание аспекта используется в dev-режиме, чтобы можно было проверить мобильную верстку без Telegram-сессии и без реального backend-ответа.",
  })),
};

const LOCAL_DEV_PDF_BYTES = new Uint8Array([
  0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x34, 0x0a, 0x31, 0x20, 0x30,
  0x20, 0x6f, 0x62, 0x6a, 0x0a, 0x3c, 0x3c, 0x2f, 0x54, 0x79, 0x70, 0x65,
  0x2f, 0x43, 0x61, 0x74, 0x61, 0x6c, 0x6f, 0x67, 0x2f, 0x50, 0x61, 0x67,
  0x65, 0x73, 0x20, 0x32, 0x20, 0x30, 0x20, 0x52, 0x3e, 0x3e, 0x0a, 0x65,
  0x6e, 0x64, 0x6f, 0x62, 0x6a, 0x0a, 0x32, 0x20, 0x30, 0x20, 0x6f, 0x62,
  0x6a, 0x0a, 0x3c, 0x3c, 0x2f, 0x54, 0x79, 0x70, 0x65, 0x2f, 0x50, 0x61,
  0x67, 0x65, 0x73, 0x2f, 0x43, 0x6f, 0x75, 0x6e, 0x74, 0x20, 0x30, 0x3e,
  0x3e, 0x0a, 0x65, 0x6e, 0x64, 0x6f, 0x62, 0x6a, 0x0a, 0x74, 0x72, 0x61,
  0x69, 0x6c, 0x65, 0x72, 0x0a, 0x3c, 0x3c, 0x2f, 0x52, 0x6f, 0x6f, 0x74,
  0x20, 0x31, 0x20, 0x30, 0x20, 0x52, 0x3e, 0x3e, 0x0a, 0x25, 0x25, 0x45,
  0x4f, 0x46, 0x0a,
]);

function withLocalDevBirthData(
  user: UserProfile,
  body: {
    birth_date?: string;
    birth_time_known?: boolean;
    birth_city?: string;
  },
): UserProfile {
  return {
    ...user,
    birth_city: body.birth_city || user.birth_city,
    birth_time_known: body.birth_time_known ?? user.birth_time_known,
    sun_sign: user.sun_sign || "virgo",
  };
}

async function requestLocalDevFixture<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T | undefined> {
  if (!shouldUseLocalDevFixtures()) return undefined;

  await new Promise((resolve) => window.setTimeout(resolve, 120));

  if (path === "/users/me" && method === "POST") {
    return localDevUser as T;
  }

  if (path === "/users/me/gender" && method === "POST") {
    const gender =
      body && typeof body === "object" && "gender" in body
        ? String((body as { gender?: unknown }).gender ?? "")
        : localDevUser.gender;
    localDevUser = { ...localDevUser, gender };
    return localDevUser as T;
  }

  if (path === "/users/me/birth" && method === "POST") {
    localDevUser = withLocalDevBirthData(
      localDevUser,
      (body ?? {}) as {
        birth_date?: string;
        birth_time_known?: boolean;
        birth_city?: string;
      },
    );
    return {
      ok: true,
      city_resolved: localDevUser.birth_city,
    } as T;
  }

  if (path === "/natal/summary" && method === "GET") {
    return {
      ...localDevSummary,
      birth_city: localDevUser.birth_city,
      birth_time_known: localDevUser.birth_time_known,
    } as T;
  }

  if (path === "/natal/full" && method === "GET") {
    return localDevFull as T;
  }

  if (path === "/natal/descriptions" && method === "GET") {
    return localDevDescriptions as T;
  }

  if (path === "/natal/pdf-link" && method === "POST") {
    return {
      download_url: "/natal/pdf",
      filename: "natal-chart-dev.pdf",
      expires_in: 300,
    } as T;
  }

  if (path === "/natal/pdf-send" && method === "POST") {
    return {
      status: "sent",
      filename: "natal-chart-dev.pdf",
    } as T;
  }

  return undefined;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const localFixture = await requestLocalDevFixture<T>(method, path, body);
  if (localFixture !== undefined) return localFixture;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Init-Data": WebApp.initData || "", // Telegram auth token
  };

  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const payload = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail?: unknown }).detail
        : undefined;
    throw new ApiError(
      response.status,
      formatApiErrorDetail(detail, response.statusText),
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

async function requestBlob(path: string): Promise<Blob> {
  if (shouldUseLocalDevFixtures() && path === "/natal/pdf") {
    return new Blob([LOCAL_DEV_PDF_BYTES], { type: "application/pdf" });
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    method: "GET",
    headers: {
      "X-Init-Data": WebApp.initData || "",
    },
  });

  if (!response.ok) {
    const payload = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail?: unknown }).detail
        : undefined;
    throw new ApiError(
      response.status,
      formatApiErrorDetail(detail, response.statusText),
    );
  }

  return response.blob();
}

// ── Users ──────────────────────────────────────────────────────────────────────
export const usersApi = {
  upsertMe: () => request<import("@/types").UserProfile>("POST", "/users/me"),
  setGender: (gender: string) =>
    request<import("@/types").UserProfile>("POST", "/users/me/gender", {
      gender,
    }),
  setupBirth: (data: {
    birth_date: string;
    birth_time_known: boolean;
    birth_city: string;
    lat?: number;
    lng?: number;
  }) => request("POST", "/users/me/birth", data),
  setPushEnabled: (enabled: boolean) =>
    request<import("@/types").UserProfile>("PATCH", "/users/me/push", {
      enabled,
    }),
  getPurchases: () =>
    request<import("@/types").MyPurchasesResponse>(
      "GET",
      "/users/me/purchases",
    ),
};

// ── Horoscope ──────────────────────────────────────────────────────────────────
export const horoscopeApi = {
  getToday: (sign?: string) =>
    request<import("@/types").HoroscopeResponse>(
      "GET",
      sign ? `/horoscope/today?sign=${sign}` : "/horoscope/today",
    ),
  getPeriod: (period: string, sign?: string) =>
    request<import("@/types").HoroscopeResponse>(
      "GET",
      sign
        ? `/horoscope/period?period=${period}&sign=${sign}`
        : `/horoscope/period?period=${period}`,
    ),
  getMoon: () =>
    request<import("@/types").MoonPhaseResponse>("GET", "/horoscope/moon"),
  getMoonCalendar: (year: number, month: number) =>
    request<{
      year: number;
      month: number;
      days: import("@/types").MoonCalendarDay[];
    }>("GET", `/horoscope/moon/calendar?year=${year}&month=${month}`),
};

// ── Natal ──────────────────────────────────────────────────────────────────────
export const natalApi = {
  getSummary: () =>
    request<import("@/types").NatalSummaryResponse>("GET", "/natal/summary"),
  getFull: () =>
    request<import("@/types").NatalFullResponse>("GET", "/natal/full"),
  getDescriptions: () =>
    request<import("@/types").NatalDescriptionsResponse>(
      "GET",
      "/natal/descriptions",
    ),
  downloadPdf: async () => {
    const filename = "natal-chart.pdf";

    if (canUseTelegramOpenLink()) {
      try {
        await request<NatalPdfSendResponse>("POST", "/natal/pdf-send");
        WebApp.showAlert?.("PDF-отчёт отправлен вам в чат с ботом.");
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) {
          throw error;
        }

        const blob = await requestBlob("/natal/pdf");
        triggerBlobDownload(blob, filename);
      }
      return;
    }

    try {
      const blob = await requestBlob("/natal/pdf");
      triggerBlobDownload(blob, filename);
      return;
    } catch (directDownloadError) {
      const popup = openDownloadWindow();

      try {
        const link = await request<NatalPdfLinkResponse>(
          "POST",
          "/natal/pdf-link",
        );
        const downloadUrl = apiUrl(link.download_url);

        if (popup && !popup.closed) {
          popup.location.href = downloadUrl;
          return;
        }

        triggerDownload(downloadUrl, link.filename || filename);
      } catch {
        if (popup && !popup.closed) {
          popup.close();
        }
        throw directDownloadError;
      }
    }
  },
};

// ── Tarot ──────────────────────────────────────────────────────────────────────
// Prefer backend's full card art. Local SVGs are fallback-only.
const TAROT_IMAGE_BASE =
  "https://ip-194-99-21-53-142250.vps.hosted-by-mvps.net/static/tarot/";

const TAROT_CARD_ORDER = [
  "The Fool",
  "The Magician",
  "The High Priestess",
  "The Empress",
  "The Emperor",
  "The Hierophant",
  "The Lovers",
  "The Chariot",
  "Strength",
  "The Hermit",
  "Wheel of Fortune",
  "Justice",
  "The Hanged Man",
  "Death",
  "Temperance",
  "The Devil",
  "The Tower",
  "The Star",
  "The Moon",
  "The Sun",
  "Judgement",
  "The World",
  "Ace of Wands",
  "Two of Wands",
  "Three of Wands",
  "Four of Wands",
  "Five of Wands",
  "Six of Wands",
  "Seven of Wands",
  "Eight of Wands",
  "Nine of Wands",
  "Ten of Wands",
  "Page of Wands",
  "Knight of Wands",
  "Queen of Wands",
  "King of Wands",
  "Ace of Cups",
  "Two of Cups",
  "Three of Cups",
  "Four of Cups",
  "Five of Cups",
  "Six of Cups",
  "Seven of Cups",
  "Eight of Cups",
  "Nine of Cups",
  "Ten of Cups",
  "Page of Cups",
  "Knight of Cups",
  "Queen of Cups",
  "King of Cups",
  "Ace of Swords",
  "Two of Swords",
  "Three of Swords",
  "Four of Swords",
  "Five of Swords",
  "Six of Swords",
  "Seven of Swords",
  "Eight of Swords",
  "Nine of Swords",
  "Ten of Swords",
  "Page of Swords",
  "Knight of Swords",
  "Queen of Swords",
  "King of Swords",
  "Ace of Pentacles",
  "Two of Pentacles",
  "Three of Pentacles",
  "Four of Pentacles",
  "Five of Pentacles",
  "Six of Pentacles",
  "Seven of Pentacles",
  "Eight of Pentacles",
  "Nine of Pentacles",
  "Ten of Pentacles",
  "Page of Pentacles",
  "Knight of Pentacles",
  "Queen of Pentacles",
  "King of Pentacles",
] as const;

function remoteTarotImageByName(nameEn: string | null | undefined): string | null {
  if (!nameEn) return null;
  const idx = TAROT_CARD_ORDER.indexOf(nameEn as (typeof TAROT_CARD_ORDER)[number]);
  if (idx < 0) return null;
  return `${TAROT_IMAGE_BASE}${String(idx).padStart(2, "0")}_${nameEn.replace(/ /g, "_")}.svg`;
}

function rewriteCardImage<
  T extends { image_url?: string | null; name_en?: string | null },
>(card: T): T {
  // Prefer backend-supplied URL; fall back to name-based reconstruction only
  // if backend didn't set one (e.g. legacy reading rows).
  const imageUrl = card.image_url ?? remoteTarotImageByName(card.name_en);
  return { ...card, image_url: imageUrl };
}

function rewriteSpread<T extends { cards: { image_url?: string | null }[] }>(
  resp: T,
): T {
  return { ...resp, cards: resp.cards.map(rewriteCardImage) } as T;
}

export const tarotApi = {
  draw: (spread_type: string) =>
    request<import("@/types").TarotSpreadResponse>("POST", "/tarot/draw", {
      spread_type,
    }).then(rewriteSpread),
  interpret: (reading_id: number) =>
    request<import("@/types").TarotInterpretationResponse>(
      "POST",
      `/tarot/interpret/${reading_id}`,
    ),
  history: () =>
    request<import("@/types").TarotHistoryItem[]>("GET", "/tarot/history"),
  celticStatus: () =>
    request<{
      free_remaining: number;
      free_limit: number;
      has_purchased: boolean;
      is_premium: boolean;
      needs_gate: boolean;
    }>("GET", "/tarot/celtic/status"),
  getReading: (reading_id: number) =>
    request<import("@/types").TarotSpreadResponse>(
      "GET",
      `/tarot/readings/${reading_id}`,
    ).then(rewriteSpread),
};

// ── News ───────────────────────────────────────────────────────────────────────
export const newsApi = {
  list: (params?: { category?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.category) qs.set("category", params.category);
    if (params?.limit) qs.set("limit", String(params.limit));
    const tail = qs.toString() ? `?${qs.toString()}` : "";
    return request<import("@/types").NewsPreview[]>("GET", `/news${tail}`);
  },
  get: (id: number) =>
    request<import("@/types").NewsItem>("GET", `/news/${id}`),
};

// ── Glossary ───────────────────────────────────────────────────────────────────
export const glossaryApi = {
  list: (params?: { category?: string; q?: string }) => {
    const qs = new URLSearchParams();
    if (params?.category) qs.set("category", params.category);
    if (params?.q) qs.set("q", params.q);
    const tail = qs.toString() ? `?${qs.toString()}` : "";
    return request<import("@/types").GlossaryTermShort[]>(
      "GET",
      `/glossary${tail}`,
    );
  },
  get: (slug: string) =>
    request<import("@/types").GlossaryTermFull>("GET", `/glossary/${slug}`),
};

// ── Synastry ───────────────────────────────────────────────────────────────────
export const synastryApi = {
  createRequest: () =>
    request<import("@/types").SynastryRequestOut>("POST", "/synastry/request"),
  pending: () =>
    request<import("@/types").SynastryPending[]>("GET", "/synastry/pending"),
  inviteInfo: (token: string) =>
    request<import("@/types").SynastryInviteInfo>(
      "GET",
      `/synastry/invite/${token}`,
    ),
  accept: (token: string) =>
    request<import("@/types").SynastryResult>(
      "POST",
      `/synastry/accept/${token}`,
    ),
  result: (id: number) =>
    request<import("@/types").SynastryResult>("GET", `/synastry/result/${id}`),
  manual: (payload: import("@/types").SynastryManualInput) =>
    request<import("@/types").SynastryResult>(
      "POST",
      "/synastry/manual",
      payload,
    ),
  history: () =>
    request<import("@/types").SynastryHistoryItem[]>(
      "GET",
      "/synastry/history",
    ),
  hideHistoryItem: (id: number) =>
    request<void>("DELETE", `/synastry/history/${id}`),
};

// ── Transits ───────────────────────────────────────────────────────────────────
export const transitsApi = {
  getCurrent: () =>
    request<import("@/types").TransitsResponse>("GET", "/transits/current"),
  getByDate: (date: string) =>
    request<import("@/types").TransitsResponse>(
      "GET",
      `/transits/date?date=${date}`,
    ),
  getDetails: (payload: {
    transit_planet: string;
    natal_planet: string;
    aspect: string;
  }) =>
    request<import("@/types").TransitDetails>(
      "POST",
      "/transits/details",
      payload,
    ),
  getWeek: () =>
    request<import("@/types").PeriodEventsResponse>("GET", "/transits/week"),
  getMonth: () =>
    request<import("@/types").PeriodEventsResponse>("GET", "/transits/month"),
};

// ── Payments ───────────────────────────────────────────────────────────────────
export const macApi = {
  draw: () =>
    request<import("@/types").MacReadingResponse>("POST", "/mac/draw"),
  today: () => request<import("@/types").MacTodayResponse>("GET", "/mac/today"),
  // 48-card deck flow — log a pick (card content stays client-side)
  pick: (body: { card_number: number; card_name: string; category: string }) =>
    request<import("@/types").MacPickResponse>("POST", "/mac/pick", body),
  picks: () =>
    request<import("@/types").MacPickHistoryItem[]>("GET", "/mac/picks"),
};

export const referralsApi = {
  getMe: () =>
    request<import("@/types").ReferralInfoResponse>("GET", "/referrals/me"),
  apply: (code: string) =>
    request<import("@/types").ApplyReferralResponse>("POST", "/referrals/apply", {
      code,
    }),
};

export const paymentsApi = {
  getProducts: () =>
    request<import("@/types").ProductInfo[]>("GET", "/payments/products"),
  createInvoice: (product_id: string) =>
    request<{ invoice_url: string; product_id: string; stars_amount: number }>(
      "POST",
      "/payments/invoice",
      { product_id },
    ),
};

// ── Destiny Matrix ──────────────────────────────────────────────────────────
// Структура соответствует MATRIX_DESTINY_SPEC.md §4.2 + §5.1.

export interface DestinyPersonality {
  day: number;
  month: number;
  year: number;
  bottom: number;
  center: number;
}

export interface DestinyAncestralSquare {
  top_left: number;
  top_right: number;
  bottom_right: number;
  bottom_left: number;
}

export interface DestinyLines {
  sky: number;
  earth: number;
  father: number;
  mother: number;
}

export interface DestinyPurposes {
  personal: number;
  social: number;
  spiritual: number;
  planetary: number;
}

export interface DestinyChannels {
  karmic_tail: number[];
  talents: number[];
  relationships: number[];
  finance: number[];
  material_karma: number[];
  parental: number[];
  ancestral_father_talents: number[];
  ancestral_father_karma: number[];
  ancestral_mother_talents: number[];
  ancestral_mother_karma: number[];
}

export interface DestinyVarna {
  varnas: Record<string, number>; // {"Брахман": 40, "Кшатрий": 40, ...}
  expression: number;
}

export interface DestinyCenters {
  personal: number;
  lineage: number;
  holistic: number;
}

export interface DestinyPurposesFull {
  sky_personal: number;
  earth_personal: number;
  holistic_personal: number;
  father_line: number;
  mother_line: number;
  holistic_lineage: number;
  personal_divine: number;
  divine_mission: number;
}

export interface DestinyChakraSet {
  sahasrara: number;
  adjna: number;
  vishuddha: number;
  anahata: number;
  manipura: number;
  svadhisthana: number;
  muladhara: number;
}

export interface DestinyChakras {
  sky: DestinyChakraSet;
  earth: DestinyChakraSet;
}

export interface DestinyHealthRow {
  chakra: string;
  energy: number;
  physics: number;
  key: number;
}

export interface DestinyHealthMap {
  rows: DestinyHealthRow[];
  system: { energy: number; physics: number; key: number };
}

export interface DestinyEntries {
  money: number;
  partner: number;
}

export interface DestinySpecials {
  talent: number;
  character: number;
  money: number;
  love: number;
  cross: number;
  comfort: number[]; // [comfort_a, comfort_b] = [reduce(2B+2C), reduce(2B+C)]
  love_diag_1?: number; // reduce(cross + love) — зеркало money_diag_1
}

export interface DestinyFamilyLines {
  male_upper: number[];   // [near_center, near_corner] к TL
  male_lower: number[];   // [near_center, near_corner] к BR
  female_upper: number[]; // [near_center, near_corner] к TR
  female_lower: number[]; // [near_center, near_corner] к BL
}

export interface DestinyMatrixPositions {
  personality: DestinyPersonality;
  ancestral_square: DestinyAncestralSquare;
  lines: DestinyLines;
  purposes: DestinyPurposes;
  channels: DestinyChannels;
  varna: DestinyVarna;
  /** Новые поля по спеке Ладини — опциональные на время миграции */
  centers?: DestinyCenters;
  purposes_full?: DestinyPurposesFull;
  chakras?: DestinyChakras;
  health_map?: DestinyHealthMap;
  entries?: DestinyEntries;
  specials?: DestinySpecials;
  money_diagonal?: number[];
  family_lines?: DestinyFamilyLines;
}

export interface DestinyMatrixResponse {
  positions: DestinyMatrixPositions;
  birth_date: string;
  computed_at: string;
  has_full_access: boolean;
}

export interface ArcanaResponse {
  arcana_num: number;
  arcana_name: string;
  keywords: string[];
  contexts: Record<string, string>;
}

export interface DestinyMatrixInterpretation {
  reading_id: number;
  sections: Record<string, string>;
  model: string;
  generated_at: string;
  /** V2: false означает что показаны только секции из `FREE_SECTIONS`,
   *  остальные ключи есть в `sections` с teaser-текстом и помечены в `locked_sections`. */
  has_full_access?: boolean;
  locked_sections?: string[];
}

export const destinyApi = {
  calculate: () =>
    request<DestinyMatrixResponse>("POST", "/destiny-matrix/calculate"),
  getMe: () =>
    request<DestinyMatrixResponse>("GET", "/destiny-matrix/me"),
  getArcana: (num: number) =>
    request<ArcanaResponse>("GET", `/destiny-matrix/arcana/${num}`),
  getInterpretation: () =>
    request<DestinyMatrixInterpretation>("GET", "/destiny-matrix/interpretation"),
  downloadPdf: async () => {
    const filename = "destiny-matrix.pdf";

    if (canUseTelegramOpenLink()) {
      try {
        await request<NatalPdfSendResponse>("POST", "/destiny-matrix/pdf-send");
        WebApp.showAlert?.("PDF-отчёт отправлен вам в чат с ботом.");
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) {
          throw error;
        }
        const blob = await requestBlob("/destiny-matrix/pdf");
        triggerBlobDownload(blob, filename);
      }
      return;
    }

    try {
      const blob = await requestBlob("/destiny-matrix/pdf");
      triggerBlobDownload(blob, filename);
      return;
    } catch (directDownloadError) {
      const popup = openDownloadWindow();
      try {
        const link = await request<NatalPdfLinkResponse>(
          "POST",
          "/destiny-matrix/pdf-link",
        );
        const downloadUrl = apiUrl(link.download_url);
        if (popup && !popup.closed) {
          popup.location.href = downloadUrl;
          return;
        }
        triggerDownload(downloadUrl, link.filename || filename);
      } catch {
        if (popup && !popup.closed) {
          popup.close();
        }
        throw directDownloadError;
      }
    }
  },
};

export { ApiError };
