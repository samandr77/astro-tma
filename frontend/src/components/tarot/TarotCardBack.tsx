type Props = { width?: number | string; height?: number | string }

export function TarotCardBack({ width = '100%', height = '100%' }: Props) {
  return (
    <img
      src="/tarot-back.jpg"
      alt=""
      aria-hidden="true"
      width={typeof width === 'number' ? width : undefined}
      height={typeof height === 'number' ? height : undefined}
      style={{
        display: 'block',
        width,
        height,
        objectFit: 'contain',
      }}
      draggable={false}
    />
  )
}
