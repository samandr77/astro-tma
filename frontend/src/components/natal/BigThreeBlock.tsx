import { motion } from "framer-motion";
import { ZODIAC_SIGNS, type NatalSummaryResponse } from "@/types";
import { ZodiacIcon } from "@/components/ui/ZodiacIcon";
import type { ZodiacSign } from "@/components/NatalChart/types";

type BigThreeKind = "sun" | "moon" | "ascendant";

interface BigThreeBlockProps {
  summary: NatalSummaryResponse;
  onOpenSheet: (kind: BigThreeKind) => void;
  onOpenProfile: () => void;
}

const META: Record<
  BigThreeKind,
  { label: string; glyph: string; metaphor: string; color: string }
> = {
  sun: {
    label: "СОЛНЦЕ",
    glyph: "☉",
    metaphor: "Как я сияю",
    color: "var(--gold)",
  },
  moon: {
    label: "ЛУНА",
    glyph: "☽",
    metaphor: "Как я чувствую",
    color: "#c6d5e8",
  },
  ascendant: {
    label: "ВОСХОД",
    glyph: "↗",
    metaphor: "Как я выгляжу",
    color: "#e8b4a8",
  },
};

const SIGN_RU_FROM_RAW: Record<string, string> = {};
for (const s of ZODIAC_SIGNS) {
  SIGN_RU_FROM_RAW[s.value] = s.label;
  SIGN_RU_FROM_RAW[s.value.charAt(0).toUpperCase() + s.value.slice(1)] = s.label;
}

function signValue(signRaw: string | null | undefined): ZodiacSign | null {
  if (!signRaw) return null;
  const lower = signRaw.toLowerCase();
  return (ZODIAC_SIGNS.find((s) => s.value === lower)?.value as ZodiacSign | undefined) ?? null;
}

function signLabelRu(signRaw: string | null | undefined): string | null {
  if (!signRaw) return null;
  return SIGN_RU_FROM_RAW[signRaw] ?? SIGN_RU_FROM_RAW[signRaw.toLowerCase()] ?? signRaw;
}

function BigThreeCard({
  kind,
  sign,
  isUnknown,
  delay,
  onClick,
}: {
  kind: BigThreeKind;
  sign: string | null;
  isUnknown?: boolean;
  delay: number;
  onClick: () => void;
}) {
  const meta = META[kind];
  const showUnknown = kind === "ascendant" && isUnknown;
  const ru = signLabelRu(sign);

  return (
    <motion.button
      type="button"
      className="natal-big-three__card"
      style={{ borderColor: meta.color }}
      onClick={onClick}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
      whileTap={{ scale: 0.97 }}
    >
      <span
        className="natal-big-three__kind-glyph"
        style={{ color: meta.color }}
      >
        {meta.glyph}
      </span>
      <span className="natal-big-three__label">{meta.label}</span>
      {showUnknown ? (
        <>
          <span className="natal-big-three__unknown">Не рассчитан</span>
          <span className="natal-big-three__metaphor">
            Укажите время рождения
          </span>
        </>
      ) : (
        <>
          <span
            className="natal-big-three__sign-glyph"
            style={{ color: meta.color }}
          >
            {(() => {
              const sv = signValue(sign);
              return sv ? <ZodiacIcon sign={sv} size={26} /> : "✦";
            })()}
          </span>
          <span className="natal-big-three__sign">{ru ?? "—"}</span>
          <span className="natal-big-three__metaphor">{meta.metaphor}</span>
        </>
      )}
    </motion.button>
  );
}

export function BigThreeBlock({
  summary,
  onOpenSheet,
  onOpenProfile,
}: BigThreeBlockProps) {
  const isAscUnknown = !summary.birth_time_known;
  return (
    <div className="natal-big-three">
      <div className="natal-big-three__heading">Ваше ядро</div>
      <div className="natal-big-three__grid">
        <BigThreeCard
          kind="sun"
          sign={summary.sun_sign}
          delay={0}
          onClick={() => onOpenSheet("sun")}
        />
        <BigThreeCard
          kind="moon"
          sign={summary.moon_sign}
          delay={0.08}
          onClick={() => onOpenSheet("moon")}
        />
        <BigThreeCard
          kind="ascendant"
          sign={summary.ascendant_sign}
          isUnknown={isAscUnknown}
          delay={0.16}
          onClick={() =>
            isAscUnknown ? onOpenProfile() : onOpenSheet("ascendant")
          }
        />
      </div>
    </div>
  );
}
