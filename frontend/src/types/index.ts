// ── API Response types (mirror backend Pydantic schemas) ──────────────────────

export interface UserProfile {
  id: number;
  name: string;
  gender: string | null;
  sun_sign: string | null;
  birth_city: string | null;
  birth_time_known: boolean;
  push_enabled: boolean;
  is_premium: boolean;
  created_at: string;
}

export interface PurchaseItem {
  product_id: string;
  product_name: string;
  status: string;
  stars_amount: number;
  created_at: string | null;
}

export interface SubscriptionItem {
  plan: string;
  status: string;
  stars_paid: number;
  starts_at: string | null;
  expires_at: string | null;
  is_trial?: boolean;
  trial_reason?: string | null;
}

export interface MyPurchasesResponse {
  purchases: PurchaseItem[];
  subscriptions: SubscriptionItem[];
  active_subscription: SubscriptionItem | null;
}

export interface ReferralStats {
  invited_total: number;
  purchased: number;
  days_earned: number;
}

export interface ReferralInfoResponse {
  code: string;
  invite_url: string;
  stats: ReferralStats;
}

export interface ApplyReferralResponse {
  success: boolean;
  days_granted: number;
  message: string;
}

export interface EnergyScores {
  love: number;
  career: number;
  health: number;
  luck: number;
}

export interface HoroscopeResponse {
  sign: string;
  sign_ru: string;
  date: string;
  period: string;
  text_ru: string;
  energy: EnergyScores;
  is_personalised: boolean;
}

export interface MoonPhaseResponse {
  phase_name: string;
  phase_name_ru: string;
  emoji: string;
  description_ru: string;
  illumination: number;
  date: string;
  favorable_actions?: string[];
  avoid_actions?: string[];
}

export interface MoonCalendarDay {
  day: number;
  phase_name: string;
  phase_name_ru: string;
  emoji: string;
  illumination: number;
  favorable_actions?: string[];
  avoid_actions?: string[];
}

export interface TarotCardDetail {
  id: number;
  name_ru: string;
  name_en: string;
  emoji: string;
  arcana: string;
  reversed: boolean;
  meaning_ru: string;
  position_name_ru: string;
  position_meaning_ru: string | null;
  keywords_ru: string[];
  image_url?: string | null;
}

export interface TarotSpreadResponse {
  reading_id: number;
  spread_type: string;
  cards: TarotCardDetail[];
  is_premium: boolean;
  next_reset_at?: string | null;
  reused_existing?: boolean;
  period_type?: "daily" | "weekly" | string | null;
}

export interface TarotPositionNarrative {
  n: number;
  narrative: string;
}

export interface TarotInterpretationResponse {
  reading_id: number;
  spread_type: string;
  positions: TarotPositionNarrative[];
  summary: string;
}

export interface TarotHistoryItem {
  reading_id: number;
  spread_type: string;
  card_count: number;
  card_previews: string[];
  created_at: string;
}

export interface NatalPlanetData {
  degree: number; // absolute 0–360
  sign_degree: number; // within-sign 0–30
  sign: string;
  house: number;
  retrograde: boolean;
}

export interface NatalHouseData {
  number: number;
  degree: number;
  sign: string;
}

export interface NatalAspectData {
  p1: string;
  p2: string;
  aspect: string;
  orb: number;
}

export type NatalElementKey = "fire" | "earth" | "air" | "water";
export type NatalModalityKey = "cardinal" | "fixed" | "mutable";

export interface NatalElementsDistribution {
  fire: number;
  earth: number;
  air: number;
  water: number;
  dominant: NatalElementKey;
  dominant_ru: string;
  deficient: NatalElementKey | null;
  deficient_ru: string | null;
}

export interface NatalModalitiesDistribution {
  cardinal: number;
  fixed: number;
  mutable: number;
  dominant: NatalModalityKey;
  dominant_ru: string;
}

export interface NatalDominantPlanet {
  planet: string;
  planet_ru: string;
  score: number;
  reason: string;
}

export interface NatalDominants {
  elements: NatalElementsDistribution;
  modalities: NatalModalitiesDistribution;
  planet: NatalDominantPlanet;
  retrograde_planets: string[];
}

export interface NatalHeroInfo {
  headline: string;
  subline: string;
}

export interface NatalHeroInfoMap {
  elements: NatalHeroInfo;
  planets: NatalHeroInfo;
  houses: NatalHeroInfo;
  aspects: NatalHeroInfo;
}

export interface NatalKeyAspect extends NatalAspectData {
  key_score?: number;
}

export interface NatalSummaryResponse {
  has_chart: boolean;
  sun_sign: string | null;
  moon_sign: string | null;
  ascendant_sign: string | null;
  mc_sign: string | null;
  birth_city: string | null;
  birth_time_known: boolean;
  birth_lat: number | null;
  birth_lng: number | null;
  birth_tz: string | null;
  birth_date: string | null;
  birth_time: string | null;
  planets?: Record<string, NatalPlanetData>;
  houses?: NatalHouseData[];
  aspects?: NatalAspectData[];
  dominants?: NatalDominants | null;
  key_aspects?: NatalKeyAspect[];
  hero_info?: NatalHeroInfoMap | null;
}

export interface PlanetData {
  sign: string;
  sign_ru: string;
  degree: number;
  sign_degree: number;
  house: number;
  retrograde: boolean;
  speed: number;
}

export interface NatalFullResponse {
  sun_sign: string;
  moon_sign: string;
  ascendant_sign: string | null;
  planets: Record<string, PlanetData>;
  houses: { number: number; sign: string; sign_ru: string; degree: number }[];
  aspects: {
    p1: string;
    p2: string;
    aspect: string;
    orb: number;
    applying: boolean;
  }[];
  interpretations: { planet: string; category: string; text: string }[];
  reading: string | null;
}

export interface NatalDescriptionEntry {
  short: string;
  full: string;
}

export interface NatalAspectDescription {
  p1: string;
  p2: string;
  type: string;
  short: string;
  full: string;
}

export interface NatalDescriptionsResponse {
  planets: Record<string, NatalDescriptionEntry>;
  houses: Record<string, NatalDescriptionEntry>;
  aspects: NatalAspectDescription[];
}

export interface NewsPreview {
  id: number;
  date: string;
  title_ru: string;
  category: string;
  priority: number;
  preview: string;
}

export interface NewsItem {
  id: number;
  date: string;
  title_ru: string;
  body_md: string;
  category: string;
  priority: number;
}

export interface GlossaryTermShort {
  slug: string;
  title_ru: string;
  category: string;
  short_ru: string;
}

export interface GlossaryTermFull {
  slug: string;
  title_ru: string;
  category: string;
  short_ru: string;
  full_ru: string;
  related: GlossaryTermShort[];
}

export interface SynastryAspectOut {
  p1_name: string;
  p2_name: string;
  p1_name_ru: string;
  p2_name_ru: string;
  aspect: string;
  aspect_ru: string;
  orb: number;
  weight: number;
}

export interface SynastryScores {
  love: number;
  communication: number;
  trust: number;
  passion: number;
  overall: number;
}

export interface SynastryPlanetInfo {
  name: string;
  name_ru: string;
  sign: string;
  sign_ru: string;
  degree: number;
  sign_degree: number;
  house: number;
  retrograde: boolean;
}

export interface SynastryHouseInfo {
  number: number;
  sign: string;
  sign_ru: string;
  degree: number;
}

export interface SynastryAspectInterp {
  p1_name: string;
  p2_name: string;
  p1_name_ru: string;
  p2_name_ru: string;
  aspect: string;
  aspect_ru: string;
  orb: number;
  text_ru: string;
}

export interface SynastryResult {
  id: number | null;
  aspects: SynastryAspectOut[];
  scores: SynastryScores;
  total_aspects: number;
  initiator_name: string | null;
  partner_name: string | null;
  is_initiator: boolean;
  planets_a: SynastryPlanetInfo[];
  planets_b: SynastryPlanetInfo[];
  houses_a: SynastryHouseInfo[];
  houses_b: SynastryHouseInfo[];
  interpretations: SynastryAspectInterp[];
  summary_ru: string | null;
  created_at: string | null;
}

export interface SynastryHistoryItem {
  id: number;
  partner_name: string | null;
  is_initiator: boolean;
  scores: SynastryScores;
  total_aspects: number;
  created_at: string;
}

export interface SynastryRequestOut {
  id: number;
  token: string;
  invite_url: string;
  status: string;
  expires_at: string;
  initiator_name: string | null;
}

export interface SynastryPending {
  id: number;
  token: string;
  initiator_name: string;
  expires_at: string;
}

export interface SynastryInviteInfo {
  initiator_name: string | null;
  status: string;
  expires_at: string;
  is_own: boolean;
  is_expired: boolean;
}

export type TransitCategory =
  | "support"
  | "tension"
  | "transformation"
  | "neutral";

export interface TransitAspect {
  transit_planet: string;
  natal_planet: string;
  aspect: string;
  orb: number;
  weight: number;
  transit_planet_ru: string;
  natal_planet_ru: string;
  aspect_ru: string;
  transit_retrograde?: boolean;
  applying?: boolean | null;
  text_ru?: string | null;
  category: TransitCategory;
}

export interface RetrogradeInfo {
  planet: string;
  planet_ru: string;
  glyph: string;
  sign: string;
  sign_ru: string;
  description_ru: string;
}

export interface SynastryManualInput {
  partner_name: string;
  birth_date: string; // YYYY-MM-DD
  birth_time: string; // HH:MM
  birth_time_known: boolean;
  birth_city: string;
  birth_lat?: number;
  birth_lng?: number;
  birth_tz?: string;
}

export interface SkyPosition {
  sign: string;
  sign_ru: string;
  degree: number;
  retrograde: boolean;
}

export interface TransitsResponse {
  date: string;
  aspects: TransitAspect[];
  energy: EnergyScores;
  sky: Record<string, SkyPosition>;
  retrogrades: RetrogradeInfo[];
}

export interface TransitDetails {
  text_ru: string;
  advice_do: string | null;
  advice_avoid: string | null;
  affected_house: number | null;
  affected_house_topic: string | null;
}

export interface PeriodEvent {
  date: string; // YYYY-MM-DD
  kind: "aspect" | "ingress";
  title_ru: string;
  category: TransitCategory;
  weight: number;
  // Aspect-specific
  transit_planet?: string | null;
  natal_planet?: string | null;
  aspect?: string | null;
  transit_planet_ru?: string | null;
  natal_planet_ru?: string | null;
  aspect_ru?: string | null;
  orb?: number | null;
  text_ru?: string | null;
  // Ingress-specific
  planet?: string | null;
  planet_ru?: string | null;
  from_sign?: string | null;
  from_sign_ru?: string | null;
  to_sign?: string | null;
  to_sign_ru?: string | null;
}

export interface PeriodEventsResponse {
  start_date: string;
  end_date: string;
  events: PeriodEvent[];
}

export interface MacCardResponse {
  id: number;
  name_ru: string;
  category: string;
  emoji: string;
  description_ru: string;
  question_ru: string;
  affirmation_ru: string;
  image_url?: string | null;
}

export interface MacReadingResponse {
  reading_id: number;
  card: MacCardResponse;
}

export interface MacPickHistoryItem {
  pick_id: number;
  card_number: number;
  card_name: string;
  category: string;
  created_at: string;
}

export interface MacPickResponse extends MacPickHistoryItem {
  next_reset_at: string;
  reused_existing: boolean;
}

export interface MacTodayResponse {
  pick: MacPickHistoryItem | null;
  next_reset_at: string;
}

export interface ProductInfo {
  id: string;
  name: string;
  description: string;
  stars: number;
  type: string;
}

export type ZodiacSign =
  | "aries"
  | "taurus"
  | "gemini"
  | "cancer"
  | "leo"
  | "virgo"
  | "libra"
  | "scorpio"
  | "sagittarius"
  | "capricorn"
  | "aquarius"
  | "pisces";

export const ZODIAC_SIGNS: {
  value: ZodiacSign;
  label: string;
  emoji: string;
  dates: string;
}[] = [
  { value: "aries", label: "Овен", emoji: "♈", dates: "21 мар — 19 апр" },
  { value: "taurus", label: "Телец", emoji: "♉", dates: "20 апр — 20 май" },
  { value: "gemini", label: "Близнецы", emoji: "♊", dates: "21 май — 20 июн" },
  { value: "cancer", label: "Рак", emoji: "♋", dates: "21 июн — 22 июл" },
  { value: "leo", label: "Лев", emoji: "♌", dates: "23 июл — 22 авг" },
  { value: "virgo", label: "Дева", emoji: "♍", dates: "23 авг — 22 сен" },
  { value: "libra", label: "Весы", emoji: "♎", dates: "23 сен — 22 окт" },
  {
    value: "scorpio",
    label: "Скорпион",
    emoji: "♏",
    dates: "23 окт — 21 ноя",
  },
  {
    value: "sagittarius",
    label: "Стрелец",
    emoji: "♐",
    dates: "22 ноя — 21 дек",
  },
  {
    value: "capricorn",
    label: "Козерог",
    emoji: "♑",
    dates: "22 дек — 19 янв",
  },
  {
    value: "aquarius",
    label: "Водолей",
    emoji: "♒",
    dates: "20 янв — 18 фев",
  },
  { value: "pisces", label: "Рыбы", emoji: "♓", dates: "19 фев — 20 мар" },
];
