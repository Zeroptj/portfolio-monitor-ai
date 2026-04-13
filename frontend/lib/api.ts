import axios from "axios"
import type {
  Holding, PortfolioSummary, Metrics,
  Allocation, OptimizerResult, RebalanceCheck,
  NewsArticle, AISummary,
} from "@/types/portfolio"

const api = axios.create({ baseURL: "/api" })

// ── Holdings ────────────────────────────────────────────
export const getHoldings  = (): Promise<Holding[]> =>
  api.get("/holdings").then(r => r.data)

export const addHolding = (data: {
  symbol: string; name: string; asset_type: string
  quantity: number; cost: number; exchange?: string
}): Promise<{ id: number; symbol: string }> =>
  api.post("/holdings", data).then(r => r.data)

export const updateHolding = (
  id: number, data: { quantity?: number; cost?: number }
): Promise<unknown> =>
  api.patch(`/holdings/${id}`, data).then(r => r.data)

export const deleteHolding = (id: number): Promise<unknown> =>
  api.delete(`/holdings/${id}`).then(r => r.data)

// ── Prices ───────────────────────────────────────────────
export const getPrices = (): Promise<Record<string, number>> =>
  api.get("/prices").then(r => r.data)

export const getFxRate = (): Promise<{ rate: number }> =>
  api.get("/prices/fx").then(r => r.data)

export const refreshPrices = (): Promise<{
  ok: boolean; symbols: string[]; prices: Record<string, number>
  updated: string[]; fresh: string[]; message: string
}> => api.post("/prices/refresh").then(r => r.data)

// ── Portfolio ────────────────────────────────────────────
export const getPortfolioSummary = (): Promise<PortfolioSummary> =>
  api.get("/portfolio/summary").then(r => r.data)

export const getPortfolioMetrics = (days = 365): Promise<Metrics> =>
  api.get(`/portfolio/metrics?days=${days}`).then(r => r.data)

export const getAssetMetrics = (symbol: string, days = 365): Promise<Metrics> =>
  api.get(`/portfolio/metrics?symbol=${symbol}&days=${days}`).then(r => r.data)

export const getAllocation = (): Promise<Allocation> =>
  api.get("/portfolio/allocation").then(r => r.data)

// ── Optimizer ────────────────────────────────────────────
export const runOptimizer = (
  model: string = "all"
): Promise<Record<string, OptimizerResult>> =>
  api.post("/optimizer/run", { model }).then(r => r.data)

export const getRebalanceCheck = (): Promise<RebalanceCheck> =>
  api.get("/optimizer/rebalance").then(r => r.data)

// ── AI ───────────────────────────────────────────────────
export const getAIStatus = (): Promise<{ enabled: boolean }> =>
  api.get("/ai/status").then(r => r.data)

export const getAISummary = (refresh = false): Promise<AISummary> =>
  api.get(`/ai/summary${refresh ? "?refresh=true" : ""}`).then(r => r.data)

export const getRecommendation = (question: string): Promise<{ answer: string }> =>
  api.post("/ai/recommend", { question }).then(r => r.data)

export const getAIAllocationInsight = (): Promise<{ insight: string }> =>
  api.get("/ai/allocation").then(r => r.data)

export const getAIOptimizerAdvice = (): Promise<{ advice: string; results: Record<string, unknown> }> =>
  api.post("/ai/optimizer-advice").then(r => r.data)

// ── News ─────────────────────────────────────────────────
export const getNews = (symbol?: string): Promise<NewsArticle[]> =>
  api.get(`/news${symbol ? `?symbol=${symbol}` : ""}`).then(r => r.data)
