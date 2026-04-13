"use client"

import { useEffect, useState } from "react"
import { getAllocation, getAIAllocationInsight } from "@/lib/api"
import { useAIEnabled } from "@/lib/ai-context"
import { Allocation } from "@/types/portfolio"
import AllocationPie from "@/components/charts/AllocationPie"
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

export default function AllocationPage() {
  const aiEnabled  = useAIEnabled()
  const [alloc,      setAlloc     ] = useState<Allocation | null>(null)
  const [loading,    setLoading   ] = useState(true)
  const [aiInsight,  setAiInsight ] = useState<string>("")
  const [aiLoading,  setAiLoading ] = useState(false)

  useEffect(() => {
    getAllocation()
      .then(setAlloc)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 240, color: "#333", fontSize: 11, letterSpacing: "2px" }}>
        LOADING...
      </div>
    )
  }

  if (!alloc) {
    return (
      <div>
        <div style={PAGE_TITLE}>Allocation</div>
        <div style={{ color: "#333", fontSize: 12, padding: 40, textAlign: "center" }}>
          No allocation data. Add holdings first.
        </div>
      </div>
    )
  }

  const assetBars: BarItem[] = Object.entries(alloc.by_asset ?? {})
    .sort(([, a], [, b]) => b - a)
    .map(([name, value]) => ({ name, value }))

  const sectorBars: BarItem[] = Object.entries(alloc.by_sector ?? {})
    .sort(([, a], [, b]) => b - a)
    .map(([name, value]) => ({ name, value }))

  const exposureBars: BarItem[] = Object.entries(alloc.by_exposure ?? {})
    .sort(([, a], [, b]) => b - a)
    .map(([name, value]) => ({ name, value }))

  const regionBars: BarItem[] = Object.entries(alloc.by_region ?? {})
    .sort(([, a], [, b]) => b - a)
    .map(([name, value]) => ({ name, value }))

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div style={PAGE_TITLE}>Allocation</div>
        {aiEnabled && (
          <button
            onClick={async () => {
              setAiLoading(true)
              try { setAiInsight((await getAIAllocationInsight()).insight) }
              catch { setAiInsight("Error — could not get AI insight.") }
              finally { setAiLoading(false) }
            }}
            disabled={aiLoading}
            style={{
              background: aiLoading ? "transparent" : "#fff",
              color:      aiLoading ? "#6B7280" : "#000",
              border:     "1px solid #333",
              padding:    "7px 20px",
              fontSize:   10,
              fontWeight: 700,
              letterSpacing: "1px",
              cursor:     aiLoading ? "wait" : "pointer",
            }}
          >
            {aiLoading ? "ANALYZING..." : "✦ ANALYZE"}
          </button>
        )}
      </div>

      {aiInsight && (
        <div style={{ background: "#111", border: "1px solid #222", padding: "16px 20px", marginBottom: 1 }}>
          <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: "1.5px", textTransform: "uppercase", color: "#6B7280", marginBottom: 10 }}>
            ✦ AI Allocation Insight
          </div>
          <div style={{ color: "#B3B3B3", fontSize: 13, lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
            {aiInsight}
          </div>
        </div>
      )}

      {/* By Type + By Asset */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1 }}>
        <div style={PANEL}>
          <AllocationPie data={alloc.by_type} label="By Asset Type" />
        </div>
        <div style={PANEL}>
          <AllocationPie data={alloc.by_asset} label="By Asset" />
        </div>
      </div>

      {/* Asset bar */}
      {assetBars.length > 0 && (
        <>
          <div style={SECTION_LABEL}>Weight by Asset</div>
          <div style={PANEL}>
            <BarComparison data={assetBars} label="Weight" suffix="%" />
          </div>
        </>
      )}

      {/* Sector */}
      {sectorBars.length > 0 && (
        <>
          <div style={SECTION_LABEL}>Weight by Sector</div>
          <div style={PANEL}>
            <BarComparison data={sectorBars} label="Weight" suffix="%" />
          </div>
        </>
      )}

      {/* Exposure (bond ETFs) */}
      {exposureBars.length > 0 && (
        <>
          <div style={SECTION_LABEL}>Fixed Income Exposure</div>
          <div style={PANEL}>
            <BarComparison data={exposureBars} label="Weight" suffix="%" />
          </div>
        </>
      )}

      {/* Region */}
      {regionBars.length > 0 && (
        <>
          <div style={SECTION_LABEL}>Weight by Region</div>
          <div style={PANEL}>
            <BarComparison data={regionBars} label="Weight" suffix="%" />
          </div>
        </>
      )}

      {/* ETF Breakdown */}
      {Object.keys(alloc.by_etf ?? {}).length > 0 && (
        <>
          <div style={SECTION_LABEL}>ETF Holdings Breakdown</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))", gap: 1 }}>
            {Object.entries(alloc.by_etf).map(([etf, holdings]) => {
              const maxW = holdings.length > 0 ? Math.max(...holdings.map(h => h.weight)) : 1
              return (
                <div key={etf} style={PANEL}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 14 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "1px", color: "#fff" }}>{etf}</span>
                    <span style={{ fontSize: 9, color: "#444", letterSpacing: "0.5px" }}>
                      TOP {holdings.length} HOLDINGS
                    </span>
                  </div>

                  {holdings.length === 0 ? (
                    <div style={{ fontSize: 10, color: "#333", padding: "12px 0", letterSpacing: "0.5px" }}>
                      No data — Morningstar scrape pending
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {holdings.map((item, i) => (
                        <div key={i}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                            <span style={{ fontSize: 11, color: "#B3B3B3", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "75%" }}>
                              {item.name}
                            </span>
                            <span style={{ fontSize: 11, fontFamily: "monospace", color: "#fff", flexShrink: 0, marginLeft: 8 }}>
                              {item.weight.toFixed(2)}%
                            </span>
                          </div>
                          <div style={{ height: 2, background: "#1a1a1a" }}>
                            <div style={{
                              height: "100%",
                              width: `${(item.weight / maxW) * 100}%`,
                              background: "#fff",
                              opacity: 0.15 + (0.85 * (1 - i / Math.max(holdings.length - 1, 1))),
                            }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
