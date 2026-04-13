"use client"

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, Cell, ResponsiveContainer,
} from "recharts"

export interface BarItem {
  name: string
  value: number
  value2?: number
}

interface Props {
  data: BarItem[]
  label?: string
  label2?: string
  suffix?: string
  signColor?: boolean  // positive=white, negative=muted
}

export default function BarComparison({
  data,
  label = "Value",
  label2,
  suffix = "%",
  signColor = false,
}: Props) {
  if (!data || data.length === 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: "#333", fontSize: 12 }}>
        No data
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="1 4" stroke="#1f1f1f" vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fill: "#6B7280", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fill: "#6B7280", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v}${suffix}`}
          width={42}
        />
        <Tooltip
          contentStyle={{ background: "#111", border: "1px solid #222", borderRadius: 0, fontSize: 11 }}
          itemStyle={{ color: "#fff" }}
          formatter={(v, name) => [`${(v as number).toFixed(2)}${suffix}`, name as string]}
        />
        {label2 && (
          <Legend formatter={(v) => <span style={{ color: "#B3B3B3", fontSize: 11 }}>{v}</span>} />
        )}
        <Bar dataKey="value" name={label} fill="#fff" radius={0} maxBarSize={32}>
          {signColor && data.map((d, i) => (
            <Cell key={i} fill={d.value >= 0 ? "#fff" : "#444"} />
          ))}
        </Bar>
        {label2 && (
          <Bar dataKey="value2" name={label2} fill="#555" radius={0} maxBarSize={32} />
        )}
      </BarChart>
    </ResponsiveContainer>
  )
}
