import type { NatalSummaryResponse } from '@/types'
import type {
  NatalChartData,
  ChartBodyName,
  PlanetName,
  PlanetPosition,
  ZodiacSign,
  AspectType,
} from './types'

const VALID_ASPECT_TYPES = new Set<string>([
  'conjunction', 'opposition', 'trine', 'square', 'sextile',
])

const VALID_PLANETS = new Set<string>([
  'sun', 'moon', 'mercury', 'venus', 'mars',
  'jupiter', 'saturn', 'uranus', 'neptune', 'pluto',
  'northNode', 'chiron',
])

const ASPECT_PLANET_ALIASES: Record<string, ChartBodyName> = {
  sun: 'sun',
  moon: 'moon',
  mercury: 'mercury',
  venus: 'venus',
  mars: 'mars',
  jupiter: 'jupiter',
  saturn: 'saturn',
  uranus: 'uranus',
  neptune: 'neptune',
  pluto: 'pluto',
  chiron: 'chiron',
  northnode: 'northNode',
  truenorthnode: 'northNode',
  northlunarnode: 'northNode',
  ascendant: 'ascendant',
  descendant: 'descendant',
  mediumcoeli: 'midheaven',
  midheaven: 'midheaven',
  mc: 'midheaven',
  imumcoeli: 'imumCoeli',
  ic: 'imumCoeli',
}

function toSignLower(s: string): ZodiacSign {
  return s.toLowerCase() as ZodiacSign
}

function fromSignDegree(signDegree: number): { degree: number; minute: number } {
  const d = Math.floor(signDegree)
  const m = Math.floor((signDegree - d) * 60)
  return { degree: d, minute: m }
}

function makePlanet(data: {
  sign: string
  sign_degree: number
  house: number
  retrograde: boolean
}): PlanetPosition {
  const { degree, minute } = fromSignDegree(data.sign_degree)
  return {
    sign: toSignLower(data.sign),
    degree,
    minute,
    house: data.house,
    retrograde: data.retrograde,
  }
}

function normalizeAspectPlanet(value: string): ChartBodyName | null {
  const key = value.replace(/[\s_-]/g, '').toLowerCase()
  return ASPECT_PLANET_ALIASES[key] ?? null
}

const FALLBACK_PLANET: PlanetPosition = {
  sign: 'aries',
  degree: 0,
  minute: 0,
  house: 1,
  retrograde: false,
  hidden: true,
}

export function toNatalChartData(
  summary: NatalSummaryResponse,
): NatalChartData | null {
  if (!summary.has_chart || !summary.planets || !summary.houses) return null

  const planets = summary.planets
  const houses = summary.houses

  // Build planets record — northNode and chiron may not exist in backend data
  const planetsRecord = {} as Record<PlanetName, PlanetPosition>
  for (const name of VALID_PLANETS) {
    const raw = planets[name]
    planetsRecord[name as PlanetName] = raw ? makePlanet(raw) : FALLBACK_PLANET
  }

  // House 1 cusp = ascendant
  const h1 = houses.find(h => h.number === 1)
  const h10 = houses.find(h => h.number === 10)

  const ascSignDegree = h1 ? (h1.degree % 30 + 30) % 30 : 0
  const mcSignDegree = h10 ? (h10.degree % 30 + 30) % 30 : 0

  const ascendant: PlanetPosition = {
    sign: toSignLower(summary.ascendant_sign || h1?.sign || 'aries'),
    ...fromSignDegree(ascSignDegree),
    house: 1,
  }
  const midheaven: PlanetPosition = {
    sign: toSignLower(summary.mc_sign || h10?.sign || 'capricorn'),
    ...fromSignDegree(mcSignDegree),
    house: 10,
  }

  const mappedHouses = houses.map(h => ({
    number: h.number,
    cuspDegree: h.degree,
    sign: toSignLower(h.sign),
  }))

  const aspects = (summary.aspects ?? [])
    .map(a => ({
      ...a,
      p1: normalizeAspectPlanet(a.p1),
      p2: normalizeAspectPlanet(a.p2),
    }))
    .filter(
      (a): a is typeof a & { p1: ChartBodyName; p2: ChartBodyName } =>
        VALID_ASPECT_TYPES.has(a.aspect) &&
        a.p1 != null &&
        a.p2 != null,
    )
    .map(a => ({
      planet1: a.p1,
      planet2: a.p2,
      type: a.aspect as AspectType,
      orb: a.orb,
    }))

  return {
    name: undefined,
    birthDate: summary.birth_date?.split('T')[0] ?? '2000-01-01',
    birthTime: summary.birth_time ?? '12:00',
    birthLocation: {
      city: summary.birth_city ?? '',
      country: '',
      latitude: summary.birth_lat ?? 0,
      longitude: summary.birth_lng ?? 0,
      timezone: summary.birth_tz ?? 'UTC',
    },
    sun: planetsRecord.sun,
    ascendant,
    midheaven,
    planets: planetsRecord,
    houses: mappedHouses,
    aspects,
  }
}
