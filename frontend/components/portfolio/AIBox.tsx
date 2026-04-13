"use client"
import { useState } from "react"
import { getRecommendation } from "@/lib/api"

interface Props {
  summary?:    string
  onRefresh?:  () => void
  refreshing?: boolean
}

export default function AIBox({ summary, onRefresh, refreshing }: Props) {
  const [question, setQuestion] = useState("")
  const [answer,   setAnswer  ] = useState("")
  const [loading,  setLoading ] = useState(false)

  const ask = async () => {
    if (!question.trim()) return
    setLoading(true)
    try {
      const res = await getRecommendation(question)
      setAnswer(res.answer)
    } catch {
      setAnswer("Error — could not get response.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ background: "#111", border: "1px solid #222", padding: 24 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{
          fontSize: 9,
          fontWeight: 600,
          letterSpacing: "1.5px",
          textTransform: "uppercase",
          color: "#6B7280",
        }}>
          ✦ AI Summary
        </div>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={refreshing}
            style={{
              background: "transparent",
              border: "1px solid #222",
              color: refreshing ? "#333" : "#6B7280",
              fontSize: 9,
              fontWeight: 600,
              letterSpacing: "1px",
              padding: "4px 10px",
              cursor: refreshing ? "not-allowed" : "pointer",
            }}
          >
            {refreshing ? "REFRESHING..." : "↺ REFRESH"}
          </button>
        )}
      </div>

      {summary && (
        <div style={{
          color: "#B3B3B3",
          fontSize: 13,
          lineHeight: 1.7,
          marginBottom: 20,
          whiteSpace: "pre-wrap",
          borderBottom: "1px solid #1a1a1a",
          paddingBottom: 20,
        }}>
          {summary}
        </div>
      )}

      {/* Q&A */}
      <div style={{ display: "flex", gap: 8 }}>
        <input
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === "Enter" && ask()}
          placeholder="Ask about your portfolio..."
          style={{
            flex: 1,
            background: "#000",
            border: "1px solid #333",
            padding: "8px 12px",
            color: "#fff",
            fontSize: 12,
            outline: "none",
          }}
        />
        <button
          onClick={ask}
          disabled={loading}
          style={{
            background: "#fff",
            color: "#000",
            border: "none",
            padding: "8px 16px",
            cursor: loading ? "wait" : "pointer",
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "1px",
            opacity: loading ? 0.5 : 1,
          }}
        >
          {loading ? "..." : "ASK"}
        </button>
      </div>

      {answer && (
        <div style={{
          marginTop: 12,
          color: "#B3B3B3",
          fontSize: 12,
          lineHeight: 1.7,
          background: "#0A0A0A",
          border: "1px solid #1a1a1a",
          padding: "12px 16px",
          whiteSpace: "pre-wrap",
        }}>
          {answer}
        </div>
      )}
    </div>
  )
}
