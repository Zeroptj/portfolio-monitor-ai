"use client"

import { useEffect, useState } from "react"
import { runOptimizer, getRebalanceCheck, getAIOptimizerAdvice } from "@/lib/api"
import { useAIEnabled } from "@/lib/ai-context"
import { OptimizerResult, RebalanceCheck } from "@/types/portfolio"
import RebalanceTable from "@/components/portfolio/RebalanceTable"

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

const TH: React.CSSProperties = {
  paddingBottom: 10,
  textAlign: "left",
  fontSize: 9,
  fontWeight: 600,
  letterSpacing: "1.5px",
  textTransform: "uppercase" as const,
  color: "#6B7280",
  borderBottom: "1px solid #222",
}

const MODELS = ["max_sharpe", "hrp", "min_volatility", "risk_parity", "equal_weight"]

const MODEL_LABEL: Record<string, string> = {
  max_sharpe:     "Max Sharpe",
  hrp:            "HRP",
  min_volatility: "Min Vol",
  risk_parity:    "Risk Parity",
  equal_weight:   "Equal Weight",
}

export default function OptimizerPage() {
  const aiEnabled  = useAIEnabled()
  const [results,      setResults    ] = useState<Record<string, OptimizerResult> | null>(null)
  const [rebal,        setRebal      ] = useState<RebalanceCheck | null>(null)
  const [running,      setRunning    ] = useState(false)
  const [loading,      setLoading    ] = useState(true)
  const [activeModel,  setActiveModel] = useState<string>("max_sharpe")
  const [aiAdvice,     setAiAdvice   ] = useState<string>("")
  const [aiLoading,    setAiLoading  ] = useState(false)

  useEffect(() => {
    getRebalanceCheck()
      .then(setRebal)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const handleRun = async () => {
    setRunning(true)
    setAiAdvice("")
    try {
      const r = await runOptimizer("all")
      setResults(r)
      const best = Object.entries(r).reduce(
        (prev, [m, v]) => (!v.error && (v.sharpe_ratio ?? 0) > (prev[1].sharpe_ratio ?? 0) ? [m, v] : prev),
        Object.entries(r)[0]
      )
      if (best) setActiveModel(best[0])
      // AI advice หลัง run เสร็จ (เฉพาะตอน AI enabled)
      if (aiEnabled) {
        setAiLoading(true)
        try {
          const ai = await getAIOptimizerAdvice()
          setAiAdvice(ai.advice)
        } catch { setAiAdvice("Error — could not get AI advice.") }
        finally { setAiLoading(false) }
      }
    } catch (e) {
      console.error(e)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div style={PAGE_TITLE}>Optimizer</div>
        <button
          onClick={handleRun}
          disabled={running}
          style={{
            background: running ? "transparent" : "#fff",
            color:      running ? "#6B7280" : "#000",
            border:     running ? "1px solid #333" : "1px solid #fff",
            padding:    "7px 20px",
            fontSize:   10,
            fontWeight: 700,
            letterSpacing: "1px",
            cursor:     running ? "wait" : "pointer",
          }}
        >
          {running ? "RUNNING..." : "RUN OPTIMIZER"}
        </button>
      </div>

      {/* Rebalance Status */}
      {!loading && rebal && (
        <>
          <div style={SECTION_LABEL}>Current Drift</div>
          <div style={PANEL}>
            <div style={{ display: "flex", gap: 32, marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 9, letterSpacing: "1.5px", color: "#6B7280", textTransform: "uppercase", marginBottom: 6 }}>
                  Status
                </div>
                <div style={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "1px",
                  color:   rebal.needs_rebalance ? "#F59E0B" : "#22C55E",
                  padding: "3px 10px",
                  border:  `1px solid ${rebal.needs_rebalance ? "#F59E0B" : "#22C55E"}`,
                }}>
                  {rebal.needs_rebalance ? "REBALANCE NEEDED" : "BALANCED"}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 9, letterSpacing: "1.5px", color: "#6B7280", textTransform: "uppercase", marginBottom: 6 }}>
                  Threshold
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#fff", fontVariantNumeric: "tabular-nums" }}>
                  {(rebal.threshold_pct ?? 0).toFixed(1)}%
                </div>
              </div>
            </div>

            {/* Drift table */}
            {Object.keys(rebal.drift ?? {}).length > 0 && (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr>
                    {["Symbol", "Current %", "Drift %"].map(h => (
                      <th key={h} style={TH}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(rebal.drift)
                    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
                    .map(([symbol, drift]) => {
                      const current = (rebal.current_weights?.[symbol] ?? 0)
                      const pos = drift >= 0
                      return (
                        <tr key={symbol} style={{ borderBottom: "1px solid #1a1a1a" }}>
                          <td style={{ padding: "10px 0", fontFamily: "monospace", fontWeight: 600, color: "#fff" }}>
                            {symbol}
                          </td>
                          <td style={{ padding: "10px 8px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                            {current.toFixed(1)}%
                          </td>
                          <td style={{ padding: "10px 0", fontFamily: "monospace", color: pos ? "#fff" : "#6B7280" }}>
                            {pos ? "+" : ""}{drift.toFixed(2)}%
                          </td>
                        </tr>
                      )
                    })}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {/* AI Advice */}
      {aiEnabled && (aiLoading || aiAdvice) && (
        <>
          <div style={SECTION_LABEL}>✦ AI Optimizer Advice</div>
          <div style={{ background: "#111", border: "1px solid #222", padding: "16px 20px" }}>
            {aiLoading ? (
              <div style={{ color: "#333", fontSize: 11, letterSpacing: "2px" }}>ANALYZING...</div>
            ) : (
              <div style={{ color: "#B3B3B3", fontSize: 13, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                {aiAdvice}
              </div>
            )}
          </div>
        </>
      )}

      {/* Optimizer Results */}
      {results && (
        <>
          {/* Summary comparison table */}
          <div style={SECTION_LABEL}>Model Comparison</div>
          <div style={PANEL}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr>
                  {["Model", "Exp. Return", "Volatility", "Sharpe", ""].map(h => (
                    <th key={h} style={TH}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {MODELS.filter(m => results[m]).map(model => {
                  const r   = results[model]
                  const isActive = model === activeModel
                  const ret = r.expected_return_pct ?? 0
                  return (
                    <tr
                      key={model}
                      onClick={() => setActiveModel(model)}
                      style={{
                        borderBottom: "1px solid #1a1a1a",
                        cursor: "pointer",
                        background: isActive ? "#1a1a1a" : "transparent",
                      }}
                    >
                      <td style={{ padding: "10px 12px 10px 8px", fontFamily: "monospace", fontWeight: 700, color: isActive ? "#fff" : "#B3B3B3" }}>
                        {MODEL_LABEL[model] ?? model}
                        {isActive && <span style={{ fontSize: 8, color: "#444", marginLeft: 8, letterSpacing: "1px" }}>SELECTED</span>}
                      </td>
                      <td style={{ padding: "10px 12px 10px 0", fontFamily: "monospace", color: ret >= 0 ? "#fff" : "#6B7280" }}>
                        {ret >= 0 ? "+" : ""}{ret.toFixed(2)}%
                      </td>
                      <td style={{ padding: "10px 12px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                        {(r.expected_volatility_pct ?? 0).toFixed(2)}%
                      </td>
                      <td style={{ padding: "10px 12px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                        {(r.sharpe_ratio ?? 0).toFixed(2)}
                      </td>
                      <td style={{ padding: "10px 8px 10px 0", textAlign: "right" }}>
                        <span style={{
                          fontSize: 9, padding: "2px 8px",
                          border: `1px solid ${isActive ? "#3B82F6" : "#222"}`,
                          color:  isActive ? "#3B82F6" : "#444",
                          letterSpacing: "0.5px",
                          cursor: "pointer",
                        }}>
                          VIEW
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Selected model detail */}
          {results[activeModel] && (() => {
            const r = results[activeModel]
            return (
              <>
                <div style={{ ...SECTION_LABEL, display: "flex", alignItems: "center", gap: 12 }}>
                  <span>{MODEL_LABEL[activeModel] ?? activeModel} — Weights</span>
                  <span style={{ fontSize: 9, color: "#333" }}>{r.lookback_days}d lookback</span>
                </div>
                <div style={PANEL}>
                  {r.error ? (
                    <div style={{ color: "#6B7280", fontSize: 12 }}>{r.error}</div>
                  ) : (
                    <>
                      {/* Weight cards + bar */}
                      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
                        {Object.entries(r.weights)
                          .sort(([, a], [, b]) => b - a)
                          .map(([sym, w]) => {
                            const pct = w
                            return (
                              <div key={sym}>
                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                                  <span style={{ fontSize: 11, fontFamily: "monospace", fontWeight: 600, color: "#fff" }}>{sym}</span>
                                  <span style={{ fontSize: 11, fontFamily: "monospace", color: "#B3B3B3" }}>{pct.toFixed(1)}%</span>
                                </div>
                                <div style={{ height: 2, background: "#1a1a1a" }}>
                                  <div style={{ height: "100%", width: `${pct}%`, background: "#fff", opacity: 0.6 }} />
                                </div>
                              </div>
                            )
                          })}
                      </div>

                      {/* Rebalance plan */}
                      {r.rebalance_plan?.length > 0 && (
                        <>
                          <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: "1.5px", textTransform: "uppercase", color: "#6B7280", marginBottom: 12, paddingTop: 16, borderTop: "1px solid #1a1a1a" }}>
                            Rebalance Plan
                          </div>
                          <RebalanceTable plans={r.rebalance_plan} />
                        </>
                      )}
                    </>
                  )}
                </div>
              </>
            )
          })()}
        </>
      )}
    </div>
  )
}
