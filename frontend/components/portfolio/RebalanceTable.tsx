"use client"

import { RebalancePlan } from "@/types/portfolio"

interface Props { plans: RebalancePlan[] }

const TH: React.CSSProperties = {
  paddingBottom: 10,
  textAlign: "left",
  fontSize: 9,
  fontWeight: 600,
  letterSpacing: "1.5px",
  textTransform: "uppercase",
  color: "#6B7280",
  borderBottom: "1px solid #222",
}

export default function RebalanceTable({ plans }: Props) {
  if (!plans || plans.length === 0) {
    return (
      <p style={{ fontSize: 12, textAlign: "center", padding: "24px 0", color: "#6B7280" }}>
        No rebalance actions needed.
      </p>
    )
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {["Symbol", "Action", "Current %", "Target %", "Diff %"].map(h => (
              <th key={h} style={TH}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {plans.map((p, i) => {
            const isBuy  = p.action === "BUY"
            const isSell = p.action === "SELL"
            return (
              <tr key={i} style={{ borderBottom: "1px solid #1a1a1a" }}>
                <td style={{ padding: "10px 0", fontFamily: "monospace", fontWeight: 600, color: "#fff" }}>
                  {p.symbol}
                </td>
                <td style={{ padding: "10px 8px 10px 0" }}>
                  <span style={{
                    fontSize: 9,
                    fontWeight: 700,
                    letterSpacing: "1px",
                    padding: "3px 8px",
                    border: "1px solid #333",
                    color: isBuy ? "#fff" : isSell ? "#888" : "#555",
                  }}>
                    {p.action}
                  </span>
                </td>
                <td style={{ padding: "10px 8px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                  {p.current_pct?.toFixed(1)}%
                </td>
                <td style={{ padding: "10px 8px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                  {p.target_pct?.toFixed(1)}%
                </td>
                <td style={{
                  padding: "10px 0",
                  fontFamily: "monospace",
                  color: (p.diff_pct ?? 0) >= 0 ? "#fff" : "#6B7280",
                }}>
                  {(p.diff_pct ?? 0) >= 0 ? "+" : ""}{p.diff_pct?.toFixed(2)}%
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
