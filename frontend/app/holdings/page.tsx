"use client"

import { useEffect, useState } from "react"
import { getHoldings, getPortfolioSummary, refreshPrices } from "@/lib/api"
import { Holding, PortfolioSummary } from "@/types/portfolio"
import HoldingsTable from "@/components/portfolio/HoldingsTable"

const TYPE_COLOR: Record<string, string> = {
  stock:     "#3B82F6",
  etf:       "#06B6D4",
  crypto:    "#F59E0B",
  commodity: "#EAB308",
  other:     "#6B7280",
}

function TypeBadge({ type }: { type: string }) {
  const color = TYPE_COLOR[type] ?? TYPE_COLOR.other
  return (
    <span style={{
      fontSize: 9, padding: "2px 7px",
      border: `1px solid ${color}`,
      color, letterSpacing: "0.5px",
    }}>
      {type}
    </span>
  )
}

const PAGE_TITLE: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "2px",
  textTransform: "uppercase",
  color: "#fff",
  marginBottom: 28,
}

const SECTION_LABEL: React.CSSProperties = {
  fontSize: 9,
  fontWeight: 600,
  letterSpacing: "1.5px",
  textTransform: "uppercase",
  color: "#6B7280",
  marginBottom: 12,
}

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

export default function HoldingsPage() {
  const [holdings,    setHoldings   ] = useState<Holding[]>([])
  const [summary,     setSummary    ] = useState<PortfolioSummary | null>(null)
  const [loading,     setLoading    ] = useState(true)
  const [refreshing,  setRefreshing ] = useState(false)
  const [refreshMsg,  setRefreshMsg ] = useState("")

  const load = () => {
    Promise.all([getHoldings(), getPortfolioSummary()]).then(([h, s]) => {
      setHoldings(h)
      setSummary(s)
      setLoading(false)
    })
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    setRefreshMsg("")
    try {
      const result = await refreshPrices()
      setRefreshMsg(result.message)
      load()
    } catch {
      setRefreshMsg("Refresh failed")
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 240, color: "#333", fontSize: 11, letterSpacing: "2px" }}>
        LOADING...
      </div>
    )
  }

  const liveHoldings = summary?.holdings ?? []

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div style={{ ...PAGE_TITLE, marginBottom: 0 }}>Holdings</div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {refreshMsg && (
            <span style={{ fontSize: 10, letterSpacing: "0.5px", color: "#6B7280" }}>{refreshMsg}</span>
          )}
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            style={{
              background: "transparent",
              border: "1px solid #333",
              color: refreshing ? "#444" : "#fff",
              fontSize: 9,
              fontWeight: 600,
              letterSpacing: "1.5px",
              textTransform: "uppercase",
              padding: "7px 14px",
              cursor: refreshing ? "not-allowed" : "pointer",
            }}
          >
            {refreshing ? "REFRESHING..." : "↺ REFRESH DATA"}
          </button>
        </div>
      </div>

      {/* Live Positions */}
      {liveHoldings.length > 0 && (
        <>
          <div style={SECTION_LABEL}>Live Positions</div>
          <div style={{ background: "#111", border: "1px solid #222", padding: "20px 24px", marginBottom: 28, overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr>
                  {["Symbol", "Type", "Qty", "Avg Cost", "Price", "Value", "P&L", "P&L %", "Weight"].map(h => (
                    <th key={h} style={TH}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {liveHoldings.map(h => {
                  const pnl    = h.pnl     ?? 0
                  const pnlPct = h.pnl_pct ?? 0
                  const pos    = pnl >= 0
                  return (
                    <tr key={h.id ?? h.symbol} style={{ borderBottom: "1px solid #1a1a1a" }}>
                      <td style={{ padding: "10px 12px 10px 0", fontFamily: "monospace", fontWeight: 600, color: "#fff" }}>
                        {h.symbol}
                      </td>
                      <td style={{ padding: "10px 12px 10px 0" }}>
                        <TypeBadge type={h.asset_type} />
                      </td>
                      <td style={{ padding: "10px 12px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                        {h.quantity}
                      </td>
                      <td style={{ padding: "10px 12px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                        ${(h.cost ?? 0).toFixed(2)}
                      </td>
                      <td style={{ padding: "10px 12px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                        ${(h.price ?? 0).toFixed(2)}
                      </td>
                      <td style={{ padding: "10px 12px 10px 0", fontFamily: "monospace", color: "#fff" }}>
                        ${(h.value ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}
                      </td>
                      <td style={{ padding: "10px 12px 10px 0", fontFamily: "monospace", color: pos ? "#22C55E" : "#EF4444" }}>
                        {pos ? "+" : ""}${Math.abs(pnl).toFixed(0)}
                      </td>
                      <td style={{ padding: "10px 12px 10px 0", fontFamily: "monospace", color: pos ? "#22C55E" : "#EF4444" }}>
                        {pos ? "+" : ""}{pnlPct.toFixed(2)}%
                      </td>
                      <td style={{ padding: "10px 0", fontFamily: "monospace", color: "#6B7280" }}>
                        {(h.weight_pct ?? 0).toFixed(1)}%
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* CRUD */}
      <div style={{ background: "#111", border: "1px solid #222", padding: "20px 24px" }}>
        <HoldingsTable holdings={holdings} onRefresh={load} />
      </div>
    </div>
  )
}
