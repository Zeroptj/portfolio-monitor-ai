type Props = {
  title: string
  value: string
  sub?: string
  positive?: boolean   // true = white/bold, false = muted, undefined = neutral
}

export default function MetricCard({ title, value, sub, positive }: Props) {
  const valueColor =
    positive === true  ? "#22C55E" :
    positive === false ? "#EF4444" :
    "#fff"

  const fontWeight = positive === true ? 700 : positive === false ? 600 : 600

  return (
    <div style={{
      background: "#111",
      border: "1px solid #222",
      padding: "16px 20px",
    }}>
      <div style={{
        fontSize: 9,
        fontWeight: 600,
        letterSpacing: "1.5px",
        textTransform: "uppercase",
        color: "#6B7280",
        marginBottom: 10,
      }}>
        {title}
      </div>
      <div style={{
        fontSize: 20,
        fontWeight,
        color: valueColor,
        lineHeight: 1,
        fontVariantNumeric: "tabular-nums",
      }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 10, color: "#6B7280", marginTop: 6 }}>
          {sub}
        </div>
      )}
    </div>
  )
}
