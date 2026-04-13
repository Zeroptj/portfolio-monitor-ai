"use client"

import { useState } from "react"
import { Holding } from "@/types/portfolio"
import { addHolding, deleteHolding } from "@/lib/api"

interface Props {
  holdings: Holding[]
  onRefresh: () => void
}

const ASSET_TYPES = ["stock", "etf", "crypto", "commodity", "other"]

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

const inputStyle: React.CSSProperties = {
  background: "#000",
  border: "1px solid #333",
  padding: "8px 12px",
  color: "#fff",
  fontSize: 12,
  outline: "none",
  width: "100%",
}

export default function HoldingsTable({ holdings, onRefresh }: Props) {
  const [showForm,   setShowForm  ] = useState(false)
  const [loading,    setLoading   ] = useState(false)
  const [statusMsg,  setStatusMsg ] = useState("")
  const [form, setForm] = useState({
    symbol: "", name: "", asset_type: "stock", quantity: "", cost: "", exchange: "arcx",
  })

  const handleAdd = async () => {
    if (!form.symbol || !form.quantity || !form.cost) return
    setLoading(true)
    try {
      await addHolding({
        symbol:     form.symbol.toUpperCase(),
        name:       form.name || form.symbol.toUpperCase(),
        asset_type: form.asset_type,
        quantity:   parseFloat(form.quantity),
        cost:       parseFloat(form.cost),
        exchange:   form.asset_type === "etf" ? (form.exchange.trim() || "arcx") : undefined,
      })
      const wasEtf = form.asset_type === "etf"
      setForm({ symbol: "", name: "", asset_type: "stock", quantity: "", cost: "", exchange: "arcx" })
      setShowForm(false)
      onRefresh()
      if (wasEtf) {
        setStatusMsg("Fetching Morningstar ETF data in background...")
        setTimeout(() => setStatusMsg(""), 8000)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm("Delete this holding?")) return
    await deleteHolding(id)
    onRefresh()
  }

  const fmtNum = (n: number) =>
    new Intl.NumberFormat("en-US", { maximumFractionDigits: 4 }).format(n)
  const fmtUSD = (n: number) =>
    new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(n)

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: "1.5px", textTransform: "uppercase", color: "#6B7280" }}>
            Holdings
          </div>
          {statusMsg && (
            <span style={{ fontSize: 10, color: "#444", letterSpacing: "0.3px" }}>{statusMsg}</span>
          )}
        </div>
        <button
          onClick={() => setShowForm(p => !p)}
          style={{
            background: showForm ? "transparent" : "#22C55E",
            color: showForm ? "#6B7280" : "#000",
            border: showForm ? "1px solid #333" : "1px solid #22C55E",
            padding: "5px 14px",
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: "1px",
            cursor: "pointer",
          }}
        >
          {showForm ? "CANCEL" : "+ ADD"}
        </button>
      </div>

      {showForm && (
        <div style={{ background: "#0A0A0A", border: "1px solid #222", padding: 16, marginBottom: 20 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            {[
              { key: "symbol",   placeholder: "Symbol (e.g. BTC)" },
              { key: "name",     placeholder: "Name (optional)" },
              { key: "quantity", placeholder: "Quantity",        type: "number" },
              { key: "cost",     placeholder: "Avg Cost (USD)",  type: "number" },
            ].map(({ key, placeholder, type }) => (
              <input
                key={key}
                type={type || "text"}
                placeholder={placeholder}
                value={(form as Record<string, string>)[key]}
                onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
                style={inputStyle}
              />
            ))}
            <select
              value={form.asset_type}
              onChange={e => setForm(p => ({ ...p, asset_type: e.target.value, exchange: "arcx" }))}
              style={{ ...inputStyle, gridColumn: "1 / -1" }}
            >
              {ASSET_TYPES.map(t => (
                <option key={t} value={t} style={{ background: "#111" }}>{t}</option>
              ))}
            </select>
            {form.asset_type === "etf" && (
              <div style={{ gridColumn: "1 / -1", display: "flex", alignItems: "center", gap: 10 }}>
                <input
                  type="text"
                  placeholder="Exchange (default: arcx)"
                  value={form.exchange}
                  onChange={e => setForm(p => ({ ...p, exchange: e.target.value }))}
                  style={{ ...inputStyle, flex: 1 }}
                />
                <span style={{ fontSize: 10, color: "#6B7280", letterSpacing: "0.5px", whiteSpace: "nowrap" }}>
                  arcx · xnas · xnys
                </span>
              </div>
            )}
            <button
              onClick={handleAdd}
              disabled={loading}
              style={{
                gridColumn: "1 / -1",
                background: loading ? "transparent" : "#22C55E",
                color: loading ? "#6B7280" : "#000",
                border: "1px solid #22C55E",
                padding: "9px",
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "1px",
                cursor: loading ? "wait" : "pointer",
              }}
            >
              {loading ? "ADDING..." : "ADD HOLDING"}
            </button>
          </div>
        </div>
      )}

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
          <thead>
            <tr>
              {["Symbol", "Name", "Type", "Quantity", "Avg Cost", ""].map(h => (
                <th key={h} style={TH}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {holdings.map(h => (
              <tr key={h.id} style={{ borderBottom: "1px solid #1a1a1a" }}>
                <td style={{ padding: "10px 0", fontFamily: "monospace", fontWeight: 600, color: "#fff" }}>
                  {h.symbol}
                </td>
                <td style={{ padding: "10px 8px 10px 0", color: "#B3B3B3" }}>{h.name}</td>
                <td style={{ padding: "10px 8px 10px 0" }}>
                  <TypeBadge type={h.asset_type} />
                  {h.asset_type === "etf" && h.exchange && (
                    <span style={{
                      fontSize: 9, padding: "2px 7px",
                      border: "1px solid #1e1e1e",
                      color: "#444", letterSpacing: "0.5px", marginLeft: 4,
                    }}>
                      {h.exchange}
                    </span>
                  )}
                </td>
                <td style={{ padding: "10px 8px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                  {fmtNum(h.quantity)}
                </td>
                <td style={{ padding: "10px 8px 10px 0", fontFamily: "monospace", color: "#B3B3B3" }}>
                  {fmtUSD(h.cost)}
                </td>
                <td style={{ padding: "10px 0", textAlign: "right" }}>
                  <button
                    onClick={() => handleDelete(h.id)}
                    style={{
                      fontSize: 9,
                      padding: "3px 10px",
                      border: "1px solid #EF4444",
                      background: "transparent",
                      color: "#EF4444",
                      cursor: "pointer",
                      letterSpacing: "0.5px",
                    }}
                  >
                    DELETE
                  </button>
                </td>
              </tr>
            ))}
            {holdings.length === 0 && (
              <tr>
                <td colSpan={6} style={{ padding: "32px 0", textAlign: "center", color: "#333", fontSize: 12 }}>
                  No holdings yet. Add your first one above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
