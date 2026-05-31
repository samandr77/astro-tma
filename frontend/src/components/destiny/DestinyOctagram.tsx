import type { DestinyMatrixPositions } from "@/services/api";

/**
 * Destiny Matrix octagram — classic 8-point star.
 *
 * Geometry per spec: viewBox 600×600, center (300,300). Two overlapping
 * squares with the same circumscribed radius (~230):
 *   • DIAMOND (diagonal square): vertices at top/right/bottom/left.
 *   • STRAIGHT square (ancestral): vertices at TL/TR/BR/BL.
 *
 * Numbers come dynamically from positions; nothing is hardcoded.
 */

export type DestinyNodeId =
  | "day" | "month" | "year" | "bottom" | "center"
  | "top_left" | "top_right" | "bottom_right" | "bottom_left"
  // Cardinal лучи: top/left имеют 3 точки (включая dot3 у центра),
  // right/bottom — только 2 (третья позиция занята comfort/cross/диагональю)
  | "month_1" | "month_2" | "month_3"
  | "day_1"   | "day_2"   | "day_3"
  | "year_1"  | "year_2"
  | "bottom_1" | "bottom_2"
  // 2 dots per diagonal (3-я пока убрана)
  | "aft_1" | "aft_2"   // father talents — TL
  | "amt_1" | "amt_2"   // mother talents — TR
  | "afk_1" | "afk_2"   // father karma — BR
  | "amk_1" | "amk_2"   // mother karma — BL
  // Special points near center (variant C)
  | "comfort_a" | "comfort_b"     // [near_center, near_money] — порядок с бэка
  | "cross_p"                      // между центром и mid нижнего луча
  // Money diagonal — одна внешняя точка (cross+money), пунктир к money point
  | "money_diag_1"
  | "love_diag_1";                 // зеркало money_diag_1 — под сердечком

export interface NodeMeta {
  nodeId: DestinyNodeId;
  num: number;
  tier: "free" | "premium";
  x: number;
  y: number;
}

// ── Coordinates per spec ───────────────────────────────────────────────
const VIEW = 600;
const CX = 300;
const CY = 300;

// Diamond vertices (используются как кончики октаграммы — линии и лучи
// заканчиваются здесь)
const TOP:    [number, number] = [300,  70];
const RIGHT:  [number, number] = [530, 300];
const BOTTOM: [number, number] = [300, 530];
const LEFT:   [number, number] = [ 70, 300];
// Straight square vertices
const TL: [number, number] = [140, 140];
const TR: [number, number] = [460, 140];
const BR: [number, number] = [460, 460];
const BL: [number, number] = [140, 460];

// Позиции 8 больших узлов — вынесены ЗА октаграмму, так что внутренняя
// кромка узла (radius=26) касается кончика угла. По cardinal смещение =
// 26 px; по diagonal = 26/√2 ≈ 18.4 px (под 45°).
const NODE_OFF = 26;
const NODE_OFF_D = NODE_OFF / Math.SQRT2;
const NODE_TOP:    [number, number] = [TOP[0],               TOP[1] - NODE_OFF];
const NODE_RIGHT:  [number, number] = [RIGHT[0] + NODE_OFF,  RIGHT[1]];
const NODE_BOTTOM: [number, number] = [BOTTOM[0],            BOTTOM[1] + NODE_OFF];
const NODE_LEFT:   [number, number] = [LEFT[0] - NODE_OFF,   LEFT[1]];
const NODE_TL: [number, number] = [TL[0] - NODE_OFF_D, TL[1] - NODE_OFF_D];
const NODE_TR: [number, number] = [TR[0] + NODE_OFF_D, TR[1] - NODE_OFF_D];
const NODE_BR: [number, number] = [BR[0] + NODE_OFF_D, BR[1] + NODE_OFF_D];
const NODE_BL: [number, number] = [BL[0] - NODE_OFF_D, BL[1] + NODE_OFF_D];

// Точки на внутреннем круге для каждой из 8 «спиц» — там обрываются
// крестообразные линии идущие от центра к углам. Значение R_INNER
// определяется ниже, поэтому используем функцию.
function innerEdge(toward: [number, number]): [number, number] {
  const dx = toward[0] - CX;
  const dy = toward[1] - CY;
  const len = Math.hypot(dx, dy) || 1;
  return [CX + (dx / len) * R_INNER, CY + (dy / len) * R_INNER];
}

// Age ring sits outside the octagram
const R_AGE_RING  = 268;
const R_AGE_TICK  = 276;
const R_AGE_LABEL = 286;

/** Position a point on the segment from vertex v to center, at fraction t
 *  (t=0 at vertex, t=1 at center). */
function along(v: [number, number], t: number): [number, number] {
  return [v[0] + t * (CX - v[0]), v[1] + t * (CY - v[1])];
}

// Radii мелких «кружочков».
const R_DOT_1 = 20;  // первая точка (у угла) — крупнее
const R_DOT_2 = 17;  // вторая точка (на периметре октаграммы)
const R_DOT_3 = 14;  // спецточки внутри круга (comfort, cross, money_diag)
const R_DOT = R_DOT_2;  // default для точек без явного tier

// 1-й ярус: t = 0.09 — 10 px зазор от кончика угла.
const RAY_T_1 = 0.09;
const TOP_1   = along(TOP,    RAY_T_1);
const RIGHT_1 = along(RIGHT,  RAY_T_1);
const BOT_1   = along(BOTTOM, RAY_T_1);
const LEFT_1  = along(LEFT,   RAY_T_1);
const TL_1    = along(TL, RAY_T_1);
const TR_1    = along(TR, RAY_T_1);
const BR_1    = along(BR, RAY_T_1);
const BL_1    = along(BL, RAY_T_1);

// 3-й ярус: t = 0.62 — ближе к центру (только top/left по спеке).
const RAY_T_3 = 0.62;
const TOP_3   = along(TOP,  RAY_T_3);
const LEFT_3  = along(LEFT, RAY_T_3);

// 2-й ярус: точки на периметре октаграммы — пересечение луча с
// ближайшей границей. Cardinal лучи (M/D/Y/B → центр) пересекают сторону
// прямого квадрата (y=140, x=140, y=460, x=460). Diagonal лучи
// (atl/atr/abr/abl → центр) пересекают сторону ромба.
const TOP_2:   [number, number] = [300, 140];
const LEFT_2:  [number, number] = [140, 300];
const RIGHT_2: [number, number] = [460, 300];
const BOT_2:   [number, number] = [300, 460];
const TL_2:    [number, number] = [185, 185];  // ромб LEFT-TOP   (x+y=370)
const TR_2:    [number, number] = [415, 185];  // ромб TOP-RIGHT  (x-y=230)
const BR_2:    [number, number] = [415, 415];  // ромб RIGHT-BOT  (x+y=830)
const BL_2:    [number, number] = [185, 415];  // ромб BOT-LEFT   (y-x=230)

// ── Palette ────────────────────────────────────────────────────────────
const COLOR_LINE      = "rgba(200, 195, 180, 0.6)";   // thin grey lines
const COLOR_LINE_ACC  = "rgba(232, 200, 98, 0.75)";   // accent for diamond/square outline
const COLOR_CENTER    = "#e8c862";                    // gold — center
const COLOR_BASE      = "#e8c862";                    // gold for base nodes
const COLOR_KARMA     = "#e07b6a";                    // red — bottom/karma
const COLOR_DOT       = "rgba(232, 200, 98, 0.95)";   // small dots default
const COLOR_DOT_RED   = "#e07b6a";                    // karmic dots
const COLOR_DOT_PINK  = "#d27b9c";                    // love/comfort accent
const COLOR_DOT_ORANGE = "#e8a553";                   // money accent
const COLOR_LABEL_DIM = "rgba(220, 215, 200, 0.55)";  // muted side labels
const COLOR_FATHER    = "rgba(120, 145, 220, 0.75)";  // blue — отцовская линия
const COLOR_MOTHER    = "rgba(220, 110, 130, 0.75)";  // red — материнская
const COLOR_INNER_RING = "rgba(232, 200, 98, 0.35)";  // inner circle outline

// Inner soul-circle radius (heart, $, ЗОНА КОМФОРТА живут внутри).
const R_INNER = 155;
// Comfort dots — РОВНО ГОРИЗОНТАЛЬНО справа от центра, вплотную.
// comfort_a ближе к центру, comfort_b дальше (ближе к money point).
const COMFORT_NEAR_C   = along([530, 300], 0.85);  // ~34 px от центра
const COMFORT_NEAR_MID = along([530, 300], 0.72);  // ~64 px от центра
// cross_p — на пересечении штрихпунктира money/love с мужской диагональю
// (центр → BR), позиция (380, 380) по спеке.
const CROSS_POS: [number, number] = [380, 380];
// money_diag_1 (под знаком $, выше штрихпунктира): (429, 349) по спеке.
const MONEY_DIAG_OUTER: [number, number] = [429, 349];
// love_diag_1 (под сердечком, ниже штрихпунктира): (349, 429) по спеке.
const LOVE_DIAG_OUTER:  [number, number] = [349, 429];
// Heart icon и $ — позиции из спеки §6.1.
const HEART_POS: [number, number] = [345, 400];
const DOLLAR_POS: [number, number] = [392, 345];

// Family-line dot позиции убраны: значения линий рода дублируют
// aft_*/afk_*/amt_*/amk_* на диагональных лучах. Данные остаются
// доступными в API (positions.family_lines), но визуально не рисуются.

type NodeKind = "main-lg" | "main-md" | "dot";

interface NodeDef {
  nodeId: DestinyNodeId;
  num: number;
  tier: "free" | "premium";
  x: number;
  y: number;
  kind: NodeKind;
  color?: string;
  /** Override default radius (R_DOT for dots, fixed for main). Used to
   *  размер по yarусам: 1-я точка крупнее, 3-я меньше. */
  radius?: number;
}

function buildNodes(p: DestinyMatrixPositions): NodeDef[] {
  const per = p.personality;
  const sq  = p.ancestral_square;
  const ch  = p.channels;

  // Pull pre-computed channel arrays from the backend. Each is a 3-tuple
  // in order [near corner, middle, near center] — placed directly on
  // the ray from corner to center.
  const get3 = (arr?: number[]): [number, number, number] => {
    const a = arr ?? [];
    return [a[0] ?? 0, a[1] ?? 0, a[2] ?? 0];
  };

  // Top/left имеют 3 точки: [0]=near_corner, [1]=mid, [2]=near_center.
  // Right/bottom — только [0] и [1] (третья позиция занята спецточками).
  const [t1, t2, t3] = get3(ch.talents);      // top — M ↔ C
  const [d1, d2, d3] = get3(ch.parental);     // left — D ↔ C
  const [r1, r2] = get3(ch.material_karma);   // right — Y ↔ C
  const [b1, b2] = get3(ch.karmic_tail);      // bottom — B ↔ C
  // Diagonals — берём [0] и [1]
  const [aft1, aft2] = get3(ch.ancestral_father_talents); // TL
  const [amt1, amt2] = get3(ch.ancestral_mother_talents); // TR
  const [afk1, afk2] = get3(ch.ancestral_father_karma);   // BR
  const [amk1, amk2] = get3(ch.ancestral_mother_karma);   // BL

  // Семантические точки из бэка. Fallback на 0 если запись старая — она
  // будет пересчитана на следующем /me запросе. Backend возвращает
  // comfort в порядке [comfort_a, comfort_b] = [ближе к центру, дальше].
  const sp = p.specials;
  const comfortArr = sp?.comfort ?? [0, 0];
  const crossVal   = sp?.cross ?? 0;
  const loveDiagVal = sp?.love_diag_1 ?? 0;
  const moneyDiag  = p.money_diagonal ?? [0, 0, 0];
  const [valNearC, valNearMid] = comfortArr;
  // Family lines данные приходят в `p.family_lines`, но визуально не
  // рисуются (дублируют aft_*/afk_*/amt_*/amk_*). Доступны через API.

  // Helper: a small dot.
  //   rayTier 1 — у углов октаграммы (крупная R=R_DOT_1)
  //   rayTier 2 — на периметре октаграммы (средняя R=R_DOT_2)
  //   rayTier 3 — спецточки внутри круга (меньшая R=R_DOT_3)
  const dot = (
    nodeId: DestinyNodeId,
    num: number,
    point: [number, number],
    rayTier: 1 | 2 | 3,
    color?: string,
  ): NodeDef => ({
    nodeId, num, tier: "premium",
    x: point[0], y: point[1], kind: "dot", color,
    radius: rayTier === 1 ? R_DOT_1 : rayTier === 2 ? R_DOT_2 : R_DOT_3,
  });

  return [
    // ── Main 9 nodes ──
    // 8 угловых узлов используют NODE_* — позиции ВЫНЕСЕНЫ за октаграмму
    // так что внутренняя кромка узла касается кончика угла. Центр остаётся
    // на (CX, CY).
    { nodeId: "day",    num: per.day,    tier: "free", x: NODE_LEFT[0],   y: NODE_LEFT[1],   kind: "main-lg", color: COLOR_BASE },
    { nodeId: "month",  num: per.month,  tier: "free", x: NODE_TOP[0],    y: NODE_TOP[1],    kind: "main-lg", color: COLOR_BASE },
    { nodeId: "year",   num: per.year,   tier: "free", x: NODE_RIGHT[0],  y: NODE_RIGHT[1],  kind: "main-lg", color: COLOR_BASE },
    { nodeId: "bottom", num: per.bottom, tier: "free", x: NODE_BOTTOM[0], y: NODE_BOTTOM[1], kind: "main-lg", color: COLOR_KARMA },
    { nodeId: "center", num: per.center, tier: "free", x: CX,             y: CY,             kind: "main-md", color: COLOR_CENTER },
    { nodeId: "top_left",     num: sq.top_left,     tier: "premium", x: NODE_TL[0], y: NODE_TL[1], kind: "main-lg", color: COLOR_BASE },
    { nodeId: "top_right",    num: sq.top_right,    tier: "premium", x: NODE_TR[0], y: NODE_TR[1], kind: "main-lg", color: COLOR_BASE },
    { nodeId: "bottom_right", num: sq.bottom_right, tier: "premium", x: NODE_BR[0], y: NODE_BR[1], kind: "main-lg", color: COLOR_BASE },
    { nodeId: "bottom_left",  num: sq.bottom_left,  tier: "premium", x: NODE_BL[0], y: NODE_BL[1], kind: "main-lg", color: COLOR_BASE },

    // ── Cardinal лучи.
    //   1-й ярус (у угла) — channel[0]
    //   2-й ярус (на периметре) — channel[1] = mid (talent/character/money/love)
    //   3-й ярус (у центра, только top/left) — channel[2]
    dot("month_1", t1, TOP_1, 1),
    dot("month_2", t2, TOP_2, 2),
    dot("month_3", t3, TOP_3, 3),
    dot("day_1",   d1, LEFT_1, 1),
    dot("day_2",   d2, LEFT_2, 2),
    dot("day_3",   d3, LEFT_3, 3),
    dot("year_1",  r1, RIGHT_1, 1),
    dot("year_2",  r2, RIGHT_2, 2, COLOR_DOT_ORANGE),  // = money
    dot("bottom_1", b1, BOT_1, 1, COLOR_DOT_RED),
    dot("bottom_2", b2, BOT_2, 2, COLOR_DOT_ORANGE),  // = love

    // ── 4 diagonal лучa: то же — channel[0] и channel[1] (mid) ──
    dot("aft_1", aft1, TL_1, 1),
    dot("aft_2", aft2, TL_2, 2),
    dot("amt_1", amt1, TR_1, 1),
    dot("amt_2", amt2, TR_2, 2),
    dot("afk_1", afk1, BR_1, 1),
    dot("afk_2", afk2, BR_2, 2),
    dot("amk_1", amk1, BL_1, 1),
    dot("amk_2", amk2, BL_2, 2),

    // ── Special points (зона комфорта внутри круга) ──
    dot("comfort_a", valNearC,   COMFORT_NEAR_C,   3, COLOR_DOT_PINK),
    dot("comfort_b", valNearMid, COMFORT_NEAR_MID, 3, COLOR_DOT_PINK),
    dot("cross_p",   crossVal,   CROSS_POS,        3, COLOR_DOT_ORANGE),

    // ── Money diagonal: одна внешняя точка (cross+money). Пунктир
    // рисуется как SVG path в main render. money_diag[1]=cross и
    // money_diag[2]=money — оба дублируют другие точки. ──
    dot("money_diag_1", moneyDiag[0], MONEY_DIAG_OUTER, 3, COLOR_DOT_ORANGE),
    // ── Love diagonal: зеркало money_diag_1, под сердечком ──
    dot("love_diag_1", loveDiagVal, LOVE_DIAG_OUTER, 3, COLOR_DOT_PINK),

    // ── Family lines: УБРАНЫ — дублируют значения aft_*/afk_*/amt_*/amk_*
    // на диагональных лучах. Цветные стрелки остаются как декоративные.
    // Данные family_lines из бэка по прежнему доступны в API.
  ];
}

// ── Age ring (5..75, узлы на серединах декад как на эталоне) ──────────
const AGE_NODE_YEARS = [5, 15, 25, 35, 45, 55, 65, 75];
// Минорные тики на каждом году кроме узловых
const AGE_MINOR_YEARS = Array.from({ length: 80 }, (_, i) => i + 1)
  .filter((y) => !AGE_NODE_YEARS.includes(y));

function polarFromCenter(angleDeg: number, radius: number): [number, number] {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return [CX + radius * Math.cos(rad), CY + radius * Math.sin(rad)];
}

function ageAngle(years: number): number {
  // 80-year ring starting at "5 лет" position which is approximately at
  // angle 90° (left of center) by matritsa-sudbi.ru convention. Each year
  // spans 360/80 = 4.5°. Year 5 sits at the left vertex.
  return (180 + years * 4.5) % 360;
}

function AgeRing() {
  return (
    <g data-part="age-ring">
      <circle cx={CX} cy={CY} r={R_AGE_RING}
        fill="none" stroke="rgba(232,200,98,0.35)" strokeWidth="0.9" />
      {AGE_MINOR_YEARS.map((y) => {
        const ang = ageAngle(y);
        const inner = polarFromCenter(ang, R_AGE_RING);
        const outer = polarFromCenter(ang, R_AGE_TICK - 2);
        return (
          <line key={`min-${y}`}
            x1={inner[0]} y1={inner[1]} x2={outer[0]} y2={outer[1]}
            stroke="rgba(232,200,98,0.3)" strokeWidth="0.45" />
        );
      })}
      {AGE_NODE_YEARS.map((y) => {
        const ang = ageAngle(y);
        const inner = polarFromCenter(ang, R_AGE_RING - 3);
        const outer = polarFromCenter(ang, R_AGE_TICK + 3);
        const labelPos = polarFromCenter(ang, R_AGE_LABEL);
        const ringPos = polarFromCenter(ang, R_AGE_RING);
        return (
          <g key={`node-${y}`}>
            <line x1={inner[0]} y1={inner[1]} x2={outer[0]} y2={outer[1]}
              stroke="rgba(232,200,98,0.85)" strokeWidth="1.4" />
            <circle cx={ringPos[0]} cy={ringPos[1]} r="3.2"
              fill="#0e0b20" stroke="rgba(232,200,98,0.9)" strokeWidth="1" />
            <text x={labelPos[0]} y={labelPos[1]}
              textAnchor="middle" dominantBaseline="central"
              fontSize="11" fill="rgba(232,200,98,0.95)" fontWeight={600}
              style={{ fontFamily: "Inter, system-ui, sans-serif" }}>
              {y} лет
            </text>
          </g>
        );
      })}
    </g>
  );
}

// ── Rendered node ──────────────────────────────────────────────────────
interface RenderedNodeProps {
  node: NodeDef;
  locked: boolean;
  active: boolean;
  faded: boolean;
  onTap: (n: NodeDef) => void;
}

function RenderedNode({ node, locked, active, faded, onTap }: RenderedNodeProps) {
  const isMain = node.kind === "main-lg" || node.kind === "main-md";
  const defaultRadius = node.kind === "main-lg" ? 26 : node.kind === "main-md" ? 22 : R_DOT;
  const radius = node.radius ?? defaultRadius;
  const tapR = Math.max(radius + 6, 18);

  const baseStroke = node.color ?? COLOR_BASE;
  const stroke = active ? COLOR_CENTER : baseStroke;
  const strokeWidth = active ? 2.6 : (isMain ? 1.8 : 0);
  const fill = isMain ? "#0e0b20" : (node.color ?? COLOR_DOT);

  const className =
    "destiny-octagram__node" +
    (active ? " is-active" : "") +
    (faded ? " is-faded" : "") +
    (locked ? " is-locked" : "");

  // Small dots: маленький обведённый кружок с числом ВНУТРИ (как
  // miniature версия большого узла).
  if (!isMain) {
    const dotStroke = node.color ?? COLOR_BASE;
    return (
      <g className={className} onClick={() => onTap(node)} style={{ cursor: "pointer" }}>
        <circle cx={node.x} cy={node.y} r={radius}
          fill="#0e0b20"
          stroke={active ? COLOR_CENTER : (locked ? "rgba(232,200,98,0.45)" : dotStroke)}
          strokeWidth={active ? 2 : 1.4} />
        {!locked && (
          <text x={node.x} y={node.y}
            textAnchor="middle" dominantBaseline="central"
            fontSize="11" fill={node.color ?? "rgba(232,200,98,0.95)"}
            fontWeight={600}
            style={{ fontFamily: "Inter, system-ui, sans-serif" }}>
            {node.num}
          </text>
        )}
        <circle cx={node.x} cy={node.y} r={tapR}
          fill="transparent" pointerEvents="all" />
      </g>
    );
  }

  // Main nodes: number inside the circle.
  // Используем dy="0.35em" + textAnchor="middle" для геометрической центровки
  // глифа в SVG — `dominantBaseline="central"` иногда даёт смещение из-за
  // метрик шрифта Playfair Display.
  const fontSize = node.kind === "main-md" ? 26 : 22;
  return (
    <g className={className} onClick={() => onTap(node)} style={{ cursor: "pointer" }}>
      <circle cx={node.x} cy={node.y} r={radius}
        fill={fill} stroke={stroke} strokeWidth={strokeWidth} />
      {locked ? (
        <text x={node.x} y={node.y} dy="0.35em" textAnchor="middle"
          fontSize="16" fill="rgba(232,200,98,0.55)">?</text>
      ) : (
        <text x={node.x} y={node.y} dy="0.35em" textAnchor="middle"
          fontSize={fontSize} fill={node.color ?? COLOR_CENTER} fontWeight={600}
          style={{ fontFamily: "Playfair Display, serif" }}>
          {node.num}
        </text>
      )}
      <circle cx={node.x} cy={node.y} r={tapR}
        fill="transparent" pointerEvents="all" />
    </g>
  );
}

// ── Diagonal-line text label, rotated so it reads along the line ───────
interface DiagLabelProps {
  from: [number, number];
  to:   [number, number];
  text: string;
  t?: number;         // fraction along the line (default 0.55)
  offset?: number;    // perpendicular offset
  color?: string;
}

function DiagLabel({ from, to, text, t = 0.55, offset = 12, color }: DiagLabelProps) {
  const x = from[0] + t * (to[0] - from[0]);
  const y = from[1] + t * (to[1] - from[1]);
  const dx = to[0] - from[0];
  const dy = to[1] - from[1];
  // Keep text upright-ish: flip rotation if it would be upside-down.
  let angle = (Math.atan2(dy, dx) * 180) / Math.PI;
  if (angle > 90) angle -= 180;
  if (angle < -90) angle += 180;
  // Offset perpendicular to the line
  const len = Math.hypot(dx, dy) || 1;
  const ox = (-dy / len) * offset;
  const oy = (dx / len) * offset;
  return (
    <text
      x={x + ox} y={y + oy}
      transform={`rotate(${angle} ${x + ox} ${y + oy})`}
      textAnchor="middle" dominantBaseline="central"
      fontSize="10" fontStyle="italic"
      fill={color ?? COLOR_LABEL_DIM}
      style={{ fontFamily: "Inter, system-ui, sans-serif", letterSpacing: "0.02em" }}
    >
      {text}
    </text>
  );
}

interface Props {
  positions: DestinyMatrixPositions;
  hasFullAccess: boolean;
  activeNodeId: DestinyNodeId | null;
  onNodeTap: (node: NodeMeta) => void;
}

// Iterative render mode while we align with the matritsa-sudbi.ru template:
//   "none"    — нет точек, только шаблон
//   "main"    — только 9 больших узлов (D, M, Y, B, C + 4 угла квадрата)
//   "rays1"   — main + первая точка каждого луча (8 шт.)
//   "rays12"  — main + первая и вторая точки (16 шт., 2-й ярус несёт
//                channel[2] = «третьи точки»)
//   "all"     — все точки (включая comfort, cross, money_diag)
const RENDER_MODE: "none" | "main" | "rays1" | "rays12" | "all" = "all";

// Node IDs точек каждого луча по ярусам.
const RAY_1_IDS: ReadonlySet<DestinyNodeId> = new Set<DestinyNodeId>([
  "month_1", "day_1", "year_1", "bottom_1",
  "aft_1", "amt_1", "afk_1", "amk_1",
]);
const RAY_2_IDS: ReadonlySet<DestinyNodeId> = new Set<DestinyNodeId>([
  "month_2", "day_2", "year_2", "bottom_2",
  "aft_2", "amt_2", "afk_2", "amk_2",
]);

export function DestinyOctagram({
  positions, hasFullAccess, activeNodeId, onNodeTap,
}: Props) {
  const allNodes = RENDER_MODE === "none" ? [] : buildNodes(positions);
  const nodes = (() => {
    if (RENDER_MODE === "main") {
      return allNodes.filter((n) => n.kind === "main-lg" || n.kind === "main-md");
    }
    if (RENDER_MODE === "rays1") {
      return allNodes.filter((n) =>
        n.kind === "main-lg" || n.kind === "main-md" || RAY_1_IDS.has(n.nodeId),
      );
    }
    if (RENDER_MODE === "rays12") {
      return allNodes.filter((n) =>
        n.kind === "main-lg" || n.kind === "main-md" ||
        RAY_1_IDS.has(n.nodeId) || RAY_2_IDS.has(n.nodeId),
      );
    }
    return allNodes;
  })();

  return (
    <svg
      viewBox={`-40 -40 ${VIEW + 80} ${VIEW + 80}`}
      className="destiny-octagram"
      role="img"
      aria-label="Октаграмма матрицы судьбы"
    >
      <AgeRing />

      {/* ── 8 внутренних спиц: от центра до края внутреннего круга
          в направлении каждого угла. Снаружи круга линии не рисуем. ── */}
      {([LEFT, RIGHT, TOP, BOTTOM, TL, TR, BR, BL] as const).map((corner, i) => {
        const edge = innerEdge(corner);
        return (
          <line key={`spoke-${i}`}
            x1={CX} y1={CY}
            x2={edge[0]} y2={edge[1]}
            stroke={COLOR_LINE} strokeWidth="1" />
        );
      })}

      {/* ── Diamond (diagonal square) outline ── */}
      <path
        d={`M ${LEFT[0]} ${LEFT[1]} L ${TOP[0]} ${TOP[1]} L ${RIGHT[0]} ${RIGHT[1]} L ${BOTTOM[0]} ${BOTTOM[1]} Z`}
        fill="none" stroke={COLOR_LINE_ACC} strokeWidth="1.3"
      />
      {/* ── Straight ancestral square outline ── */}
      <path
        d={`M ${TL[0]} ${TL[1]} L ${TR[0]} ${TR[1]} L ${BR[0]} ${BR[1]} L ${BL[0]} ${BL[1]} Z`}
        fill="none" stroke={COLOR_LINE_ACC} strokeWidth="1.3"
      />

      {/* ── Side-of-world labels (выше/ниже/сбоку новых вынесенных узлов) ── */}
      <text x={NODE_TOP[0]} y={NODE_TOP[1] - 36} textAnchor="middle"
        fontSize="14" fill={COLOR_LABEL_DIM}
        style={{ fontFamily: "Inter, system-ui, sans-serif", letterSpacing: "0.06em" }}>
        небо
      </text>
      <text x={NODE_BOTTOM[0]} y={NODE_BOTTOM[1] + 42} textAnchor="middle"
        fontSize="14" fill={COLOR_LABEL_DIM}
        style={{ fontFamily: "Inter, system-ui, sans-serif", letterSpacing: "0.06em" }}>
        небо
      </text>
      <text x={NODE_LEFT[0] - 30} y={NODE_LEFT[1]} textAnchor="end" dominantBaseline="central"
        fontSize="14" fill={COLOR_LABEL_DIM}
        style={{ fontFamily: "Inter, system-ui, sans-serif", letterSpacing: "0.06em" }}>
        земля
      </text>
      <text x={NODE_RIGHT[0] + 30} y={NODE_RIGHT[1]} textAnchor="start" dominantBaseline="central"
        fontSize="14" fill={COLOR_LABEL_DIM}
        style={{ fontFamily: "Inter, system-ui, sans-serif", letterSpacing: "0.06em" }}>
        земля
      </text>

      {/* ── Diagonal labels — родовые каналы ── */}
      <DiagLabel from={TL} to={[CX, CY]} text="род отца · таланты"  t={0.45} offset={-14} />
      <DiagLabel from={TR} to={[CX, CY]} text="род матери · таланты" t={0.45} offset={14} />
      <DiagLabel from={[CX, CY]} to={BR} text="род отца · карма"   t={0.55} offset={-14} />
      <DiagLabel from={[CX, CY]} to={BL} text="род матери · карма" t={0.55} offset={14} />

      {/* ── Inner soul circle ── */}
      <circle cx={CX} cy={CY} r={R_INNER}
        fill="none" stroke={COLOR_INNER_RING} strokeWidth="1.1" />

      {/* ── Lineage arrows внутри круга ── */}
      <defs>
        <marker id="dm-arrow-father" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={COLOR_FATHER} />
        </marker>
        <marker id="dm-arrow-mother" viewBox="0 0 10 10" refX="9" refY="5"
          markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={COLOR_MOTHER} />
        </marker>
      </defs>
      <line x1={CX - 75} y1={CY - 75} x2={CX + 75} y2={CY + 75}
        stroke={COLOR_FATHER} strokeWidth="1.6" opacity="0.85"
        markerStart="url(#dm-arrow-father)" markerEnd="url(#dm-arrow-father)" />
      <line x1={CX - 75} y1={CY + 75} x2={CX + 75} y2={CY - 75}
        stroke={COLOR_MOTHER} strokeWidth="1.6" opacity="0.85"
        markerStart="url(#dm-arrow-mother)" markerEnd="url(#dm-arrow-mother)" />

      {/* Labels на стрелках линий рода (внутри круга) */}
      <DiagLabel from={[CX - 75, CY - 75]} to={[CX, CY]}
        text="линия мужского рода" t={0.5} offset={-9} color={COLOR_FATHER} />
      <DiagLabel from={[CX + 75, CY + 75]} to={[CX, CY]}
        text="линия женского рода" t={0.5} offset={-9} color={COLOR_MOTHER} />

      {/* Штрихпунктирная диагональ от year_2 (money) до bottom_2 (love)
          через нижне-правый сектор. По спеке проходит через cross_p (380,380). */}
      {RENDER_MODE === "all" && (
        <path
          d={`M ${RIGHT_2[0]} ${RIGHT_2[1]} L ${BOT_2[0]} ${BOT_2[1]}`}
          fill="none" stroke={COLOR_DOT_ORANGE} strokeWidth="1.2"
          strokeDasharray="4 3" opacity="0.7" />
      )}

      {/* ── ЗОНА КОМФОРТА — text внутри круга ── */}
      <text x={CX} y={CY + 60} textAnchor="middle"
        fontSize="9" fill={COLOR_LABEL_DIM} fontWeight={500}
        style={{ fontFamily: "Inter, system-ui, sans-serif", letterSpacing: "0.12em" }}>
        ЗОНА КОМФОРТА
      </text>

      {/* Heart icon — позиция (345, 400) по спеке §6.1, слева от штрихпунктира */}
      <g transform={`translate(${HEART_POS[0]} ${HEART_POS[1]}) scale(0.5)`}>
        <path
          d="M 0 6 C -10 -4 -22 -4 -22 6 C -22 18 0 32 0 32 C 0 32 22 18 22 6 C 22 -4 10 -4 0 6 Z"
          fill="#e84545" />
      </g>

      {/* $ sign — позиция (392, 345) по спеке §6.1, справа от штрихпунктира */}
      <text x={DOLLAR_POS[0]} y={DOLLAR_POS[1]} textAnchor="middle"
        fontSize="22" fill="#5cb85c" fontWeight={700}
        style={{ fontFamily: "Inter, system-ui, sans-serif" }}>
        $
      </text>

      {/* ── All nodes ── */}
      {nodes.map((node) => {
        const locked = node.tier === "premium" && !hasFullAccess;
        const active = activeNodeId === node.nodeId;
        const faded = activeNodeId !== null && !active;
        return (
          <RenderedNode
            key={node.nodeId}
            node={node}
            locked={locked}
            active={active}
            faded={faded}
            onTap={(n) => onNodeTap({
              nodeId: n.nodeId, num: n.num, tier: n.tier, x: n.x, y: n.y,
            })}
          />
        );
      })}
    </svg>
  );
}

export type { NodeMeta as DestinyNodeMeta };
