import { motion } from "framer-motion";
import type { NatalHeroInfo } from "@/types";

/**
 * Compact hero block for tab tops on the Natal screen. Replaces the
 * decorative orbit illustrations with something information-bearing.
 */
export function HeroInfo({
  info,
  eyebrow,
}: {
  info: NatalHeroInfo | undefined | null;
  eyebrow?: string;
}) {
  if (!info) return null;
  return (
    <motion.div
      className="natal-hero-info"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {eyebrow && <div className="natal-hero-info__eyebrow">{eyebrow}</div>}
      <div className="natal-hero-info__headline">{info.headline}</div>
      {info.subline && (
        <div className="natal-hero-info__subline">{info.subline}</div>
      )}
    </motion.div>
  );
}
