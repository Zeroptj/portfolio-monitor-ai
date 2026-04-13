"use client"

import { useEffect, useState } from "react"
import { getPortfolioMetrics } from "@/lib/api"
import { Metrics } from "@/types/portfolio"
import MetricCard from "@/components/portfolio/MetricCard"
import BarComparison, { BarItem } from "@/components/charts/BarComparison"

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

const PERIODS = [
  { label: "1M",  days: 30 },
  { label: "3M",  days: 90 },
  { label: "6M",  days: 180 },
  { label: "1Y",  days: 365 },
  { label: "2Y",  days: 730 },
]

export default function PerformancePage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [days,    setDays   ] = useState(365)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    getPortfolioMetrics(days)
      .then(setMetrics)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [days])

  const benchmarkBars: BarItem[] = metrics?.benchmark
    ? [
        { name: "Portfolio", value: metrics.total_return_pct ?? 0 },
        { name: metrics.benchmark.benchmark, value: metrics.benchmark.benchmark_return_pct ?? 0 },
      ]
    : []

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div style={PAGE_TITLE}>Performance</div>

        {/* Period selector */}
        <div style={{ display: "flex", gap: 1 }}>
          {PERIODS.map(p => (
            <button
              key={p.days}
              onClick={() => setDays(p.days)}
              style={{
                background: days === p.days ? "#fff" : "transparent",
                color:      days === p.days ? "#000" : "#6B7280",
                border:     "1px solid #333",
                padding:    "4px 12px",
                fontSize:   10,
                fontWeight: 600,
                letterSpacing: "0.5px",
                cursor:     "pointer",
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: "#333", fontSize: 11, letterSpacing: "2px" }}>
          LOADING...
        </div>
      ) : metrics ? (
        <>
          {/* Returns */}
          <div style={SECTION_LABEL}>Returns</div>
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
              title="P&L"
              value={`${(metrics.pnl ?? 0) >= 0 ? "+" : ""}$${Math.abs(metrics.pnl ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
              positive={(metrics.pnl ?? 0) >= 0}
            />
            <MetricCard
              title="P&L %"
              value={`${(metrics.pnl_pct ?? 0) >= 0 ? "+" : ""}${(metrics.pnl_pct ?? 0).toFixed(2)}%`}
              positive={(metrics.pnl_pct ?? 0) >= 0}
            />
          </div>

          {/* Risk */}
          <div style={SECTION_LABEL}>Risk</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1 }}>
            <MetricCard
              title="Sharpe Ratio"
              value={(metrics.sharpe_ratio ?? 0).toFixed(2)}
              sub={(metrics.sharpe_ratio ?? 0) >= 1 ? "Good" : "Below 1.0"}
            />
            <MetricCard
              title="Volatility"
              value={`${(metrics.volatility_pct ?? 0).toFixed(2)}%`}
            />
            <MetricCard
              title="Max Drawdown"
              value={`${(metrics.max_drawdown_pct ?? 0).toFixed(2)}%`}
              positive={false}
            />
            <MetricCard
              title="Period"
              value={`${metrics.days}d`}
            />
          </div>

          {/* Benchmark comparison */}
          {metrics.benchmark && (
            <>
              <div style={SECTION_LABEL}>vs Benchmark — {metrics.benchmark.benchmark}</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, marginBottom: 20 }}>
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

              {benchmarkBars.length > 0 && (
                <div style={PANEL}>
                  <div style={{ ...SECTION_LABEL, marginTop: 0 }}>Return Comparison</div>
                  <BarComparison
                    data={benchmarkBars}
                    label="Portfolio"
                    suffix="%"
                    signColor
                  />
                </div>
              )}
            </>
          )}
        </>
      ) : (
        <div style={{ color: "#333", fontSize: 12, padding: 40, textAlign: "center" }}>
          No performance data. Run price fetch first.
        </div>
      )}
    </div>
  )
}
