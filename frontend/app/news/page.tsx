"use client"

import { useEffect, useState } from "react"
import { getNews } from "@/lib/api"
import { NewsArticle } from "@/types/portfolio"

const PAGE_TITLE: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "2px",
  textTransform: "uppercase",
  color: "#fff",
  marginBottom: 28,
}

const SYMBOLS = ["", "BTC", "ETH", "AAPL", "NVDA", "SPY", "QQQ"]

export default function NewsPage() {
  const [articles, setArticles] = useState<NewsArticle[]>([])
  const [symbol,   setSymbol  ] = useState("")
  const [loading,  setLoading ] = useState(true)

  useEffect(() => {
    setLoading(true)
    getNews(symbol || undefined)
      .then(setArticles)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [symbol])

  const fmt = (s: string) => {
    try {
      return new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
    } catch {
      return s
    }
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
        <div style={PAGE_TITLE}>News Feed</div>

        {/* Symbol filter */}
        <div style={{ display: "flex", gap: 1 }}>
          {SYMBOLS.map(s => (
            <button
              key={s || "all"}
              onClick={() => setSymbol(s)}
              style={{
                background:    symbol === s ? "#fff" : "transparent",
                color:         symbol === s ? "#000" : "#6B7280",
                border:        "1px solid #333",
                padding:       "4px 12px",
                fontSize:      10,
                fontWeight:    600,
                letterSpacing: "0.5px",
                cursor:        "pointer",
              }}
            >
              {s || "ALL"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, color: "#333", fontSize: 11, letterSpacing: "2px" }}>
          LOADING...
        </div>
      ) : articles.length === 0 ? (
        <div style={{ color: "#333", fontSize: 12, padding: 40, textAlign: "center" }}>
          No news available. Check NEWS_API_KEY in .env.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          {articles.map((a, i) => (
            <a
              key={i}
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "block",
                background: "#111",
                border: "1px solid #222",
                padding: "16px 20px",
                textDecoration: "none",
                color: "inherit",
                transition: "border-color .1s",
              }}
              onMouseEnter={e => (e.currentTarget.style.borderColor = "#444")}
              onMouseLeave={e => (e.currentTarget.style.borderColor = "#222")}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                {a.symbol && (
                  <span style={{
                    fontSize: 9,
                    fontWeight: 700,
                    letterSpacing: "1px",
                    padding: "2px 8px",
                    border: "1px solid #333",
                    color: "#fff",
                  }}>
                    {a.symbol}
                  </span>
                )}
                <span style={{ fontSize: 9, color: "#6B7280", letterSpacing: "0.5px" }}>
                  {a.source}
                </span>
                <span style={{ fontSize: 9, color: "#333", marginLeft: "auto" }}>
                  {fmt(a.published_at)}
                </span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "#fff", lineHeight: 1.4, marginBottom: 6 }}>
                {a.title}
              </div>
              {a.description && (
                <div style={{ fontSize: 11, color: "#6B7280", lineHeight: 1.6, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                  {a.description}
                </div>
              )}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}
