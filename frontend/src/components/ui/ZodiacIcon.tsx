import type { ZodiacSign } from '@/components/NatalChart/types';

const ZODIAC_LABEL_RU: Record<ZodiacSign, string> = {
  aries: 'Овен', taurus: 'Телец', gemini: 'Близнецы', cancer: 'Рак',
  leo: 'Лев', virgo: 'Дева', libra: 'Весы', scorpio: 'Скорпион',
  sagittarius: 'Стрелец', capricorn: 'Козерог',
  aquarius: 'Водолей', pisces: 'Рыбы',
};

/** Public URL of the canonical SVG glyph for a given zodiac sign. */
export const zodiacIconUrl = (sign: ZodiacSign) =>
  `/zodiac-glyphs/${sign}.svg`;

interface ZodiacIconProps {
  sign: ZodiacSign;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

export function ZodiacIcon({
  sign,
  size = 24,
  className,
  style,
}: ZodiacIconProps) {
  return (
    <img
      src={zodiacIconUrl(sign)}
      width={size}
      height={size}
      alt={ZODIAC_LABEL_RU[sign]}
      className={className}
      style={{ display: 'inline-block', verticalAlign: 'middle', ...style }}
      draggable={false}
    />
  );
}
