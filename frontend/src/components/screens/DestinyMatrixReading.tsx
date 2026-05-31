import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ApiError, destinyApi } from "@/services/api";
import { usePayment } from "@/hooks/usePayment";
import { useProductPrice } from "@/hooks/useProductPrice";
import { useAppStore } from "@/stores/app";
import { useHaptic, useTelegramBackButton } from "@/hooks/useTelegram";
import {
  DestinyOctagram,
  type DestinyNodeId,
  type DestinyNodeMeta,
} from "@/components/destiny/DestinyOctagram";
import { DestinyNarrative } from "@/components/destiny/DestinyNarrative";
import { DestinyPurposes } from "@/components/destiny/DestinyPurposes";
import { DestinyChannels } from "@/components/destiny/DestinyChannels";
import { DestinyVarna } from "@/components/destiny/DestinyVarna";
import { DestinyHealthMap } from "@/components/destiny/DestinyHealthMap";

// Human-friendly title shown in the bottom-sheet header for each tap-target.
// Wording follows the canonical Russian Destiny Matrix cheat-sheet so users
// see practical, concrete labels instead of geometric ones.
const NODE_TITLES_RU: Record<DestinyNodeId, string> = {
  // Big diamond + center
  day:    "Как видят вас другие — ваш портрет",
  month:  "Стиль мышления и таланты",
  year:   "Камень на пути финансового потока",
  bottom: "Главный кармический урок",
  center: "Ваш настоящий характер",
  // Small ancestral square — practical meanings
  top_left:     "Внутренний потенциал, главный талант",
  top_right:    "Как вы общаетесь, ваша подача себя",
  bottom_right: "Как улучшить поток денег в жизнь",
  bottom_left:  "Желания сердца — от чего вы радуетесь",
  // Cardinal axis: top/left имеют 3 точки, right/bottom — 2
  month_1: "Канал талантов — точка у угла",
  month_2: "Канал талантов — талант (mid)",
  month_3: "Канал талантов — точка у центра",
  year_1:  "Материальная карма — точка у угла",
  year_2:  "Точка входа денег (money)",
  bottom_1: "Кармический хвост — точка у угла",
  bottom_2: "Точка любви / входа партнёра",
  day_1: "Детско-родительский — точка у угла",
  day_2: "Детско-родительский — характер (mid)",
  day_3: "Детско-родительский — точка у центра",
  // Diagonals: 2 dots from corner toward center
  aft_1: "Род отца · таланты — точка у угла",
  aft_2: "Род отца · таланты — точка у центра",
  amt_1: "Род матери · таланты — точка у угла",
  amt_2: "Род матери · таланты — точка у центра",
  afk_1: "Род отца · карма — точка у угла",
  afk_2: "Род отца · карма — точка у центра",
  amk_1: "Род матери · карма — точка у угла",
  amk_2: "Род матери · карма — точка у центра",
  // Special points near center
  comfort_a: "Зона комфорта — ближе к центру",
  comfort_b: "Зона комфорта — ближе к деньгам",
  cross_p:   "Точка пересечения денег и отношений",
  // Money diagonal — внешняя точка (cross + money)
  money_diag_1: "Денежная диагональ — сила потока (cross + деньги)",
  // Love diagonal — зеркало money_diag_1, под сердечком (cross + love)
  love_diag_1: "Любовная диагональ — сила потока (cross + любовь)",
};

// Which `arcana_meanings.context` row to pull for the bottom-sheet copy
// when the user taps a given node.
const NODE_CONTEXT: Record<DestinyNodeId, string> = {
  day:    "personality",
  month:  "talents",
  year:   "ancestral",
  bottom: "karmic_tail",
  center: "personality",
  top_left:     "ancestral",
  top_right:    "ancestral",
  bottom_right: "ancestral",
  bottom_left:  "ancestral",
  // Cardinal axes — domain per axis
  month_1: "talents",
  month_2: "talents",
  month_3: "talents",
  year_1:  "material_karma",
  year_2:  "finance",  // mid = money entry
  bottom_1: "karmic_tail",
  bottom_2: "relationships",  // mid = love entry
  day_1: "parental",
  day_2: "parental",
  day_3: "parental",
  // Diagonals
  aft_1: "ancestral",
  aft_2: "ancestral",
  amt_1: "ancestral",
  amt_2: "ancestral",
  afk_1: "ancestral",
  afk_2: "ancestral",
  amk_1: "ancestral",
  amk_2: "ancestral",
  // Special points
  comfort_a: "personality",
  comfort_b: "personality",
  cross_p:   "finance",
  money_diag_1: "finance",
  love_diag_1: "relationships",
};

interface ActiveTap {
  num: number;
  title: string;
  context: string;
  tier: "free" | "premium";
  /** Only set when the tap came from the octagram itself; lets it
   *  highlight the active node on the SVG. */
  octagramNodeId: DestinyNodeId | null;
}

const MONTHS_RU_GEN = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];

function formatBirthDateRu(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  if (!y || !m || !d) return iso;
  return `${d} ${MONTHS_RU_GEN[m - 1]} ${y}`;
}

export function DestinyMatrixReading() {
  const { setScreen } = useAppStore();
  const { impact } = useHaptic();
  const price = useProductPrice("destiny_matrix_full") ?? 150;
  const { purchase, phase } = usePayment();
  const paying = phase === "opening" || phase === "activating";

  // Universal tap target — works for octagram nodes AND for cells in the
  // Purposes/Channels tables below.
  const [activeTap, setActiveTap] = useState<ActiveTap | null>(null);
  const [showCalcAnim, setShowCalcAnim] = useState(true);
  const [isPdfDownloading, setIsPdfDownloading] = useState(false);
  const [pdfDownloadError, setPdfDownloadError] = useState<string | null>(null);

  const goBack = () => {
    if (activeTap) {
      setActiveTap(null);
      return;
    }
    setScreen("destiny_matrix_info", "back");
  };
  useTelegramBackButton(goBack, true);

  const openTap = (tap: ActiveTap) => {
    impact("light");
    setActiveTap(tap);
  };
  const openOctagramTap = (meta: DestinyNodeMeta) => {
    openTap({
      num: meta.num,
      title: NODE_TITLES_RU[meta.nodeId] ?? meta.nodeId,
      context: NODE_CONTEXT[meta.nodeId] ?? "personality",
      tier: meta.tier,
      octagramNodeId: meta.nodeId,
    });
  };

  const calcMutation = useMutation({
    mutationFn: destinyApi.calculate,
    onSuccess: () => {
      impact("medium");
      window.setTimeout(() => setShowCalcAnim(false), 600);
    },
  });

  useEffect(() => {
    calcMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const reading = calcMutation.data;

  const { data: arcanaData, isFetching: arcanaFetching } = useQuery({
    queryKey: ["destiny-matrix", "arcana", activeTap?.num],
    queryFn: () => destinyApi.getArcana(activeTap!.num),
    enabled: activeTap !== null,
    staleTime: 1000 * 60 * 60,
  });

  const isLocked = activeTap?.tier === "premium" && !reading?.has_full_access;

  const handlePurchase = async () => {
    impact("medium");
    const ok = await purchase("destiny_matrix_full");
    if (ok) calcMutation.mutate();
  };

  const handleDownloadPdf = async () => {
    if (isPdfDownloading) return;
    impact("light");
    setIsPdfDownloading(true);
    setPdfDownloadError(null);
    try {
      await destinyApi.downloadPdf();
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.status === 402) {
          setPdfDownloadError("PDF доступен после открытия полного разбора.");
        } else if (error.status === 422) {
          setPdfDownloadError("Заполните дату рождения в профиле.");
        } else if (error.status === 403) {
          setPdfDownloadError(
            "Откройте чат с ботом (/start) и попробуйте снова.",
          );
        } else {
          setPdfDownloadError(error.message || "Не удалось подготовить PDF.");
        }
      } else {
        setPdfDownloadError("Не удалось подготовить PDF. Попробуйте ещё раз.");
      }
    } finally {
      setIsPdfDownloading(false);
    }
  };

  const meaning =
    arcanaData && activeTap ? arcanaData.contexts[activeTap.context] : null;

  return (
    <div className="screen destiny-reading-screen">
      <div className="screen-header screen-header--with-back">
        <button
          type="button"
          className="back-btn"
          onClick={goBack}
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
        <h2 className="screen-title">Ваша Матрица</h2>
      </div>

      <div className="screen-content destiny-reading__content">
        {(showCalcAnim || calcMutation.isPending) && (
          <div className="destiny-reading__calc">
            <div className="destiny-reading__calc-glow" />
            <p>{calcMutation.isPending ? "Считаем вашу матрицу…" : "Расшифровываем арканы…"}</p>
          </div>
        )}

        {calcMutation.isError && (
          <div className="destiny-reading__error">
            <p>
              Не удалось рассчитать матрицу.
              {calcMutation.error instanceof Error
                ? ` ${calcMutation.error.message}`
                : ""}
            </p>
            <button
              type="button"
              className="btn-ghost"
              onClick={() => calcMutation.mutate()}
            >
              Повторить
            </button>
          </div>
        )}

        {reading && !showCalcAnim && !calcMutation.isPending && (
          <>
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="destiny-reading__birth"
            >
              <span className="destiny-reading__birth-label">Дата рождения</span>
              <span className="destiny-reading__birth-date">
                {formatBirthDateRu(reading.birth_date)}
              </span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.5 }}
              className="destiny-reading__chart-wrap"
            >
              <DestinyOctagram
                positions={reading.positions}
                hasFullAccess={reading.has_full_access}
                activeNodeId={activeTap?.octagramNodeId ?? null}
                onNodeTap={openOctagramTap}
              />
            </motion.div>

            <div className="destiny-reading__legend">
              <span className="destiny-reading__legend-dot destiny-reading__legend-dot--free" />
              <span>Бесплатно: ядро и центр</span>
              <span className="destiny-reading__legend-dot destiny-reading__legend-dot--prem" />
              <span>Premium: углы рода и каналы</span>
            </div>

            {!reading.has_full_access && (
              <>
                <DestinyNarrative
                  enabled={true}
                  hasFullAccess={false}
                  onUpgrade={handlePurchase}
                />
                <section className="destiny-reading__upsell">
                  <h4>Откройте полный разбор</h4>
                  <p>
                    Личный 8-секционный разбор, 4 предназначения, 10 каналов
                    судьбы и варна. Один раз за {price} ⭐, доступ остаётся
                    навсегда.
                  </p>
                  <button
                    type="button"
                    className="btn-stars"
                    onClick={handlePurchase}
                    disabled={paying}
                  >
                    {paying
                      ? phase === "activating"
                        ? "Активируем доступ…"
                        : "Открываем оплату…"
                      : `Открыть за ${price} ⭐`}
                  </button>
                </section>
              </>
            )}

            {reading.has_full_access && (
              <>
                <DestinyPurposes
                  purposes={reading.positions.purposes}
                  purposesFull={reading.positions.purposes_full}
                  onTap={openTap}
                />
                <DestinyChannels
                  channels={reading.positions.channels}
                  onTap={openTap}
                />
                {reading.positions.health_map && (
                  <DestinyHealthMap
                    healthMap={reading.positions.health_map}
                    onTap={openTap}
                  />
                )}
                <DestinyVarna varna={reading.positions.varna} />
                <DestinyNarrative enabled={true} hasFullAccess={true} />

                <section className="destiny-reading__pdf">
                  <h4>Сохранить разбор</h4>
                  <p>
                    PDF-отчёт со всеми числами, октаграммой и личным разбором
                    в 8 секциях. Можно перечитать позже.
                  </p>
                  <button
                    type="button"
                    className="btn-stars"
                    onClick={handleDownloadPdf}
                    disabled={isPdfDownloading}
                    aria-busy={isPdfDownloading}
                  >
                    {isPdfDownloading
                      ? "Готовим PDF…"
                      : "Скачать PDF-отчёт"}
                  </button>
                  {pdfDownloadError && (
                    <p className="destiny-reading__pdf-error">
                      {pdfDownloadError}
                    </p>
                  )}
                </section>
              </>
            )}
          </>
        )}
      </div>

      {/* BottomSheet — tap any node or table cell to see arcana details */}
      <AnimatePresence>
        {activeTap && (
          <>
            <motion.div
              className="destiny-sheet-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setActiveTap(null)}
            />
            <motion.div
              className="destiny-sheet"
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "tween", duration: 0.28 }}
              drag="y"
              dragConstraints={{ top: 0, bottom: 0 }}
              dragElastic={0.2}
              onDragEnd={(_, info) => {
                if (info.offset.y > 80) setActiveTap(null);
              }}
            >
              <div className="destiny-sheet__handle" />
              <div className="destiny-sheet__header">
                <div className="destiny-sheet__node-tag">{activeTap.title}</div>
                <div className="destiny-sheet__arcana">
                  <span className="destiny-sheet__num">{activeTap.num}</span>
                  <div>
                    <div className="destiny-sheet__name">
                      {arcanaData?.arcana_name ?? "…"}
                    </div>
                    {arcanaData?.keywords?.length ? (
                      <div className="destiny-sheet__kw">
                        {arcanaData.keywords.slice(0, 3).join(" · ")}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>

              <div className="destiny-sheet__body">
                {arcanaFetching && <p>Открываем значение…</p>}
                {!arcanaFetching && isLocked && (
                  <>
                    <p className="destiny-sheet__blur">
                      В этой позиции аркан раскрывает важную часть вашего
                      рода и сценария отношений. Полное описание доступно
                      после открытия Premium-разбора.
                    </p>
                    <button
                      type="button"
                      className="btn-stars"
                      onClick={handlePurchase}
                      disabled={paying}
                    >
                      Открыть за {price} ⭐
                    </button>
                  </>
                )}
                {!arcanaFetching && !isLocked && meaning && (
                  <p>{meaning}</p>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
