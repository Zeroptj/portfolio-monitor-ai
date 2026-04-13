"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { getAIStatus } from "@/lib/api"

const AIContext = createContext<boolean>(false)

export function AIProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabled] = useState(false)

  useEffect(() => {
    getAIStatus()
      .then(r => setEnabled(r.enabled))
      .catch(() => setEnabled(false))
  }, [])

  return <AIContext.Provider value={enabled}>{children}</AIContext.Provider>
}

export function useAIEnabled(): boolean {
  return useContext(AIContext)
}
