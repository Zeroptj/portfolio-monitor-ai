import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import Sidebar from "@/components/layout/Sidebar"

const inter = Inter({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Portfolio Monitor",
  description: "Personal portfolio monitoring with AI",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className} style={{ display: "flex", minHeight: "100vh", background: "#000", color: "#fff" }}>
        <Sidebar />
        <main style={{ flex: 1, overflow: "auto", padding: "36px 40px", maxWidth: 1200 }}>
          {children}
        </main>
      </body>
    </html>
  )
}
