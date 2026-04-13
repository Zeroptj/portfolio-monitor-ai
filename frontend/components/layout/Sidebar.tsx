"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"

const NAV = [
  { href: "/dashboard",   label: "Dashboard",   icon: "▦" },
  { href: "/holdings",    label: "Holdings",    icon: "≡" },
  { href: "/performance", label: "Performance", icon: "↗" },
  { href: "/allocation",  label: "Allocation",  icon: "◑" },
  { href: "/optimizer",   label: "Optimizer",   icon: "⚖" },
  { href: "/news",        label: "News",        icon: "☰" },
]

export default function Sidebar() {
  const pathname = usePathname()
  return (
    <aside style={{
      width: 200,
      minHeight: "100vh",
      background: "#000",
      borderRight: "1px solid #222",
      display: "flex",
      flexDirection: "column",
      padding: "28px 0",
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ padding: "0 20px 24px", borderBottom: "1px solid #222" }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "2px", color: "#fff" }}>
          PORTFOLIO
        </div>
        <div style={{ fontSize: 10, color: "#6B7280", marginTop: 3, letterSpacing: "1px" }}>
          MONITOR AI
        </div>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "16px 0" }}>
        {NAV.map(({ href, label, icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/")
          return (
            <Link key={href} href={href} style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "9px 20px",
              marginBottom: 1,
              color: active ? "#fff" : "#6B7280",
              background: active ? "#111" : "transparent",
              borderLeft: active ? "2px solid #3B82F6" : "2px solid transparent",
              textDecoration: "none",
              fontSize: 12,
              fontWeight: active ? 600 : 400,
              letterSpacing: "0.5px",
              transition: "color .1s, background .1s",
            }}>
              <span style={{ fontSize: 13, width: 16, textAlign: "center", flexShrink: 0 }}>{icon}</span>
              {label}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div style={{
        padding: "16px 20px",
        borderTop: "1px solid #222",
        fontSize: 10,
        color: "#333",
        letterSpacing: "1px",
      }}>
        LOCAL · PERSONAL
      </div>
    </aside>
  )
}
