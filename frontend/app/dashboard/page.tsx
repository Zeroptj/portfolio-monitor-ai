"use client"

import { useEffect, useState } from "react"
import { getAISummary, getPortfolioMetrics, getPortfolioSummary } from "@/lib/api"
import { useAIEnabled } from "@/lib/ai-context"
import { PortfolioSummary, Metrics } from "@/types/portfolio"
import MetricCard from "@/components/portfolio/MetricCard"
import AIBox from "@/components/portfolio/AIBox"

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
  marginTop: 28,
}

const PANEL: React.CSSProperties = {
  background: "#111",
  border: "1px solid #222",
  padding: "20px 24px",
}

export default function DashboardPage() {
  const aiEnabled  = useAIEnabled()
  const [summary,    setSummary   ] = useState<PortfolioSummary | null>(null)
  const [metrics,    setMetrics   ] = useState<Metrics | null>(null)
  const [aiSummary,  setAiSummary ] = useState<string>("")
  const [loading,    setLoading   ] = useState(true)
  const [aiRefresh,  setAiRefresh ] = useState(false)

  useEffect(() => {
    const fetches: Promise<unknown>[] = [getPortfolioSummary(), getPortfolioMetrics()]
    if (aiEnabled) fetches.push(getAISummary())

    Promise.all(fetches)
      .then(([s, m, ai]) => {
        setSummary(s as PortfolioSummary)
        setMetrics(m as Metrics)
        if (ai) setAiSummary((ai as { summary: string }).summary)
      })
      .catch(err => console.error("Dashboard fetch error:", err))
      .finally(() => setLoading(false))
  }, [aiEnabled])

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 240, color: "#333", fontSize: 11, letterSpacing: "2px" }}>
        LOADING...
      </div>
    )
  }

  const pnl    = summary?.total_pnl ?? 0
  const pnlPct = summary?.total_pnl_pct ?? 0
  const pnlPos = pnl >= 0

  return (
    <div>
      <div style={PAGE_TITLE}>Dashboard</div>

      {/* ── Portfolio Value ── */}
      <div style={SECTION_LABEL}>Portfolio</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1 }}>
        <MetricCard
          title="Total Value"
          value={`$${(summary?.total_value ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
        />
        <MetricCard
          title="Cost Basis"
          value={`$${(summary?.total_cost ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
        />
        <MetricCard
          title="P&L"
          value={`${pnlPos ? "+" : ""}$${Math.abs(pnl).toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          positive={pnlPos}
        />
        <MetricCard
          title="P&L %"
          value={`${pnlPos ? "+" : ""}${pnlPct.toFixed(2)}%`}
          positive={pnlPos}
        />
      </div>

      {/* ── Risk Metrics ── */}
      {metrics && (
        <>
          <div style={SECTION_LABEL}>Risk Metrics</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1 }}>
            <MetricCard
              title="Total Return"
              value={`${(metrics.total_return_pct ?? 0) >= 0 ? "+" : ""}${(metrics.total_return_pct ?? 0).toFixed(2)}%`}
              positive={(metrics.total_return_pct ?? 0) >= 0}
            />
            <MetricCard
              title="Ann. Return"
              value={`${(metrics.annualized_return_pct ?? 0) >= 0 ? "+" : ""}${(metrics.annualized_return_pct ?? 0).toFixed(2)}%`}
              positive={(metrics.annualized_return_pct ?? 0) >= 0}
            />
            <MetricCard
              title="Sharpe Ratio"
              value={(metrics.sharpe_ratio ?? 0).toFixed(2)}
              sub={(metrics.sharpe_ratio ?? 0) >= 1 ? "Good" : (metrics.sharpe_ratio ?? 0) >= 0 ? "Below avg" : "Poor"}
            />
            <MetricCard
              title="Max Drawdown"
              value={`${(metrics.max_drawdown_pct ?? 0).toFixed(2)}%`}
              positive={false}
            />
          </div>
        </>
      )}

      {/* ── Benchmark ── */}
      {metrics?.benchmark?.benchmark && (
        <>
          <div style={SECTION_LABEL}>vs {metrics.benchmark.benchmark}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1 }}>
            <MetricCard
              title="Alpha"
              value={`${(metrics.benchmark.alpha_pct ?? 0) >= 0 ? "+" : ""}${(metrics.benchmark.alpha_pct ?? 0).toFixed(2)}%`}
              positive={(metrics.benchmark.alpha_pct ?? 0) >= 0}
            />
            <MetricCard
              title="Beta"
              value={(metrics.benchmark.beta ?? 0).toFixed(2)}
            />
            <MetricCard
              title="Correlation"
              value={(metrics.benchmark.correlation ?? 0).toFixed(2)}
            />
            <MetricCard
              title="Benchmark Return"
              value={`${(metrics.benchmark.benchmark_return_pct ?? 0) >= 0 ? "+" : ""}${(metrics.benchmark.benchmark_return_pct ?? 0).toFixed(2)}%`}
              positive={(metrics.benchmark.benchmark_return_pct ?? 0) >= 0}
            />
          </div>
        </>
      )}

      {/* ── Top Positions ── */}
      {(summary?.holdings?.length ?? 0) > 0 && (
        <>
          <div style={SECTION_LABEL}>Top Positions</div>
          <div style={PANEL}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr>
                  {["Symbol", "Value", "Weight", "P&L", "P&L %"].map(h => (
                    <th key={h} style={{
                      paddingBottom: 10,
                      textAlign: "left",
                      fontSize: 9,
                      fontWeight: 600,
                      letterSpacing: "1.5px",
                      textTransform: "uppercase",
                      color: "#6B7280",
                      borderBottom: "1px solid #222",
                    }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...( summary?.holdings ?? [])]
                  .sort((a, b) => (b.value ?? 0) - (a.value ?? 0))
                  .slice(0, 5)
                  .map((h, i) => {
                    const hPnl    = h.pnl    ?? 0
                    const hPnlPct = h.pnl_pct ?? 0
                    const pos     = hPnl >= 0
                    return (
                      <tr key={h.id ?? `${h.symbol}-${i}`} style={{ borderBottom: "1px solid #1a1a1a" }}>
                        <td style={{ padding: "10px 0", fontFamily: "monospace", fontWeight: 600, color: "#fff" }}>
                          {h.symbol}
                        </td>
                        <td style={{ padding: "10px 8px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                          ${(h.value ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}
                        </td>
                        <td style={{ padding: "10px 8px 10px 0", fontFamily: "monospace", color: "#6B7280" }}>
                          {(h.weight_pct ?? 0).toFixed(1)}%
                        </td>
                        <td style={{ padding: "10px 8px 10px 0", fontFamily: "monospace", color: pos ? "#fff" : "#6B7280" }}>
                          {pos ? "+" : ""}${Math.abs(hPnl).toLocaleString("en-US", { maximumFractionDigits: 0 })}
                        </td>
                        <td style={{ padding: "10px 0", fontFamily: "monospace", color: pos ? "#fff" : "#6B7280" }}>
                          {pos ? "+" : ""}{hPnlPct.toFixed(2)}%
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ── AI Box ── */}
      {aiEnabled && (
        <div style={{ marginTop: 28 }}>
          <AIBox
            summary={aiSummary}
            refreshing={aiRefresh}
            onRefresh={async () => {
              setAiRefresh(true)
              try {
                const ai = await getAISummary(true)
                setAiSummary(ai.summary)
              } catch { /* ignore */ }
              finally { setAiRefresh(false) }
            }}
          />
        </div>
      )}
    </div>
  )
}
