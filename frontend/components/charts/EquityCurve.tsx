"use client"

import {
  AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts"

interface DataPoint { date: string; value: number }

interface Props {
  data: DataPoint[]
  label?: string
}

export default function EquityCurve({ data, label = "Portfolio Value" }: Props) {
  if (!data || data.length === 0) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: "#333", fontSize: 12 }}>
        No data available
      </div>
    )
  }

  const fmt = (v: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(v)

  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={data} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor="#fff" stopOpacity={0.08} />
            <stop offset="95%" stopColor="#fff" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="1 4" stroke="#1f1f1f" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: "#6B7280", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: string) => v.slice(5)}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fill: "#6B7280", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
          width={44}
        />
        <Tooltip
          contentStyle={{ background: "#111", border: "1px solid #222", borderRadius: 0, fontSize: 12 }}
          labelStyle={{ color: "#B3B3B3" }}
          itemStyle={{ color: "#fff" }}
          formatter={(v) => [fmt(v as number), label]}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke="#fff"
          strokeWidth={1.5}
          fill="url(#equityGrad)"
          dot={false}
          activeDot={{ r: 3, fill: "#fff", strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
