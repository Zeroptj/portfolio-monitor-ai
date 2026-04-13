export type AssetType = "crypto" | "stock" | "etf" | "commodity"

export interface Holding {
  id: number
  symbol: string
  name: string
  asset_type: AssetType
  exchange?: string
  quantity: number
  cost: number
  price?: number
  value?: number
  pnl?: number
  pnl_pct?: number
  weight_pct?: number
}

export interface PortfolioSummary {
  total_value: number
  total_cost: number
  total_pnl: number
  total_pnl_pct: number
  holdings: Holding[]
  metrics: Metrics
}

export interface Metrics {
  total_return_pct: number
  annualized_return_pct: number
  sharpe_ratio: number
  volatility_pct: number
  max_drawdown_pct: number
  current_value: number
  cost_basis?: number
  pnl?: number
  pnl_pct?: number
  days: number
  benchmark?: BenchmarkMetrics
}

export interface BenchmarkMetrics {
  benchmark: string
  alpha_pct: number
  beta: number
  correlation: number
  benchmark_return_pct: number
}

export interface Allocation {
  by_asset:    Record<string, number>
  by_type:     Record<string, number>
  by_sector:   Record<string, number>
  by_exposure: Record<string, number>
  by_region:   Record<string, number>
  by_etf:      Record<string, { name: string; weight: number }[]>
}

export interface OptimizerResult {
  model: string
  weights: Record<string, number>
  expected_return_pct: number
  expected_volatility_pct: number
  sharpe_ratio: number
  lookback_days: number
  rebalance_plan: RebalancePlan[]
  error?: string
}

export interface RebalancePlan {
  symbol: string
  current_pct: number
  target_pct: number
  diff_pct: number
  action: "BUY" | "SELL" | "HOLD"
}

export interface RebalanceCheck {
  needs_rebalance: boolean
  threshold_pct: number
  current_weights: Record<string, number>
  drift: Record<string, number>
}

export interface NewsArticle {
  title: string
  description: string
  url: string
  source: string
  published_at: string
  symbol?: string
}

export interface AISummary {
  date: string
  summary: string
}
