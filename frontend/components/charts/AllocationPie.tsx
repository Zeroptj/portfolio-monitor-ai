"use client"

import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from "recharts"

// Monochrome shades
const GRAYS = ["#ffffff", "#d0d0d0", "#a0a0a0", "#707070", "#505050", "#383838", "#282828", "#1e1e1e"]

interface Props {
  data: Record<string, number>
  label?: string
}

export default function AllocationPie({ data, label }: Props) {
  const entries = Object.entries(data || {})
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a)

  if (entries.length === 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: "#333", fontSize: 12 }}>
        No data
      </div>
    )
  }

  const chartData = entries.map(([name, value]) => ({ name, value }))

  return (
    <div>
      {label && (
        <p style={{ fontSize: 9, fontWeight: 600, letterSpacing: "1.5px", textTransform: "uppercase", color: "#6B7280", marginBottom: 8 }}>
          {label}
        </p>
      )}
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="45%"
            innerRadius={52}
            outerRadius={88}
            paddingAngle={2}
            dataKey="value"
          >
            {chartData.map((_, i) => (
              <Cell key={i} fill={GRAYS[i % GRAYS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ background: "#111", border: "1px solid #222", borderRadius: 0, fontSize: 11 }}
            itemStyle={{ color: "#fff" }}
            formatter={(v) => [`${(v as number).toFixed(1)}%`]}
          />
          <Legend
            iconSize={8}
            iconType="square"
            formatter={(value) => (
              <span style={{ color: "#B3B3B3", fontSize: 11 }}>{value}</span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
