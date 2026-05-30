import { Fragment, useEffect, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import styles from "./Natal.module.css";

/**
 * Render the sheet body with **markdown bold** support and preserved
 * line breaks. Body is split on blank lines into paragraphs, each line
 * inside a paragraph becomes its own line, and `**text**` segments are
 * wrapped in <strong>. This is what makes per-aspect headings like
 * "Солнце ☌ Меркурий · орб 8.0°" stand out from the prose below them.
 */
function renderBoldInline(line: string): ReactNode[] {
  // Split on **...** preserving the inside captures
  const parts = line.split(/\*\*(.+?)\*\*/g);
  return parts.map((part, i) =>
    i % 2 === 1 ? (
      <strong key={i} className={styles.descSheetHeading}>{part}</strong>
    ) : (
      <Fragment key={i}>{part}</Fragment>
    ),
  );
}

function renderBody(body: string): ReactNode {
  const paragraphs = body.split(/\n{2,}/);
  return paragraphs.map((para, pi) => (
    <p key={pi}>
      {para.split("\n").map((line, li) => (
        <Fragment key={li}>
          {li > 0 && <br />}
          {renderBoldInline(line)}
        </Fragment>
      ))}
    </p>
  ));
}

export type NatalDescriptionSheetProps = {
  open: boolean;
  title: string;
  subtitle?: string;
  symbol?: string;
  body: string | null;
  isLoading?: boolean;
  accent?: string;
  onClose: () => void;
};

export function NatalDescriptionSheet({
  open,
  title,
  subtitle,
  symbol,
  body,
  isLoading,
  accent,
  onClose,
}: NatalDescriptionSheetProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className={styles.descSheetOverlay}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
        >
          <motion.div
            className={styles.descSheet}
            style={accent ? { borderColor: accent } : undefined}
            initial={{ scale: 0.92, opacity: 0, y: 12 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.94, opacity: 0, y: 8 }}
            transition={{ duration: 0.28, ease: [0.22, 0.61, 0.36, 1] }}
            onClick={(e) => e.stopPropagation()}
          >
            <header className={styles.descSheetHeader}>
              {symbol && (
                <span
                  className={styles.descSheetSymbol}
                  style={accent ? { color: accent } : undefined}
                  aria-hidden="true"
                >
                  {symbol}
                </span>
              )}
              <span className={styles.descSheetTitleBox}>
                <h3 style={accent ? { color: accent } : undefined}>{title}</h3>
                {subtitle && <p>{subtitle}</p>}
              </span>
              <button
                type="button"
                className={styles.descSheetClose}
                onClick={onClose}
                aria-label="Закрыть"
              >
                ×
              </button>
            </header>

            <div className={styles.descSheetBody}>
              {isLoading ? (
                <span className={styles.descSheetLoader}>
                  Готовим описание…
                </span>
              ) : body ? (
                renderBody(body)
              ) : (
                <span className={styles.descSheetLoader}>
                  Описание скоро появится.
                </span>
              )}
            </div>

            <p className={styles.descSheetFootnote}>
              Полный разбор — в скачанном PDF-отчёте.
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
