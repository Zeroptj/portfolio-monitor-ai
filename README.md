# Portfolio Monitor AI

Personal portfolio monitoring tool with AI analysis. Bloomberg-style monochrome UI, Python engine, Next.js frontend.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 15, TypeScript, Recharts |
| Backend | Python (FastAPI + CLI subprocess fallback) |
| Database | SQLite via SQLAlchemy |
| AI | Google Gemini (summary + Q&A) |
| Prices | CoinGecko (crypto), yfinance (stocks/ETF) |
| ETF Data | Morningstar (holdings, sector, region) |
| News | NewsAPI |

## Project Structure

```
portfolio-monitor-ai/
├── config.yaml              # assets, benchmark, refresh intervals, AI config
├── data/
│   └── portfolio.db         # SQLite database
├── engine/
│   ├── cli.py               # CLI entry point (Next.js subprocess calls)
│   ├── main.py              # FastAPI server (optional, faster)
│   ├── ai/
│   │   ├── summary.py       # Daily AI portfolio summary (Gemini)
│   │   └── recommender.py   # Q&A recommendations
│   ├── data/
│   │   ├── price_feed.py    # CoinGecko + yfinance price fetching
│   │   ├── morningstar.py   # ETF holdings/sector/region scraper (Playwright)
│   │   └── news_feed.py     # NewsAPI with daily DB cache
│   └── portfolio/
│       ├── holdings.py      # SQLAlchemy models + CRUD
│       ├── metrics.py       # Return, Sharpe, drawdown, alpha, beta
│       └── optimizer.py     # Max Sharpe, HRP, Min Vol, Risk Parity, Equal Weight
└── frontend/
    ├── app/                 # Next.js App Router pages
    │   ├── dashboard/       # Overview + metrics + AI summary
    │   ├── holdings/        # CRUD + live positions + data refresh
    │   ├── performance/     # Equity curve, period selector, benchmark
    │   ├── allocation/      # Pie/bar charts, sector, ETF breakdown
    │   ├── optimizer/       # 5-model optimizer + rebalance plan
    │   └── news/            # Filtered news by symbol
    ├── components/
    │   ├── charts/          # EquityCurve, AllocationPie, BarComparison
    │   ├── layout/          # Sidebar
    │   └── portfolio/       # MetricCard, HoldingsTable, AIBox, RebalanceTable
    ├── lib/
    │   ├── api.ts           # All API calls (axios)
    │   └── python.ts        # FastAPI-first, subprocess fallback
    └── types/
        └── portfolio.ts     # TypeScript interfaces
```

## Setup

### 1. Environment

Create `.env` in the project root:

```env
GEMINI_API_KEY=your_key
NEWS_API_KEY=your_key
```

### 2. Python

```bash
cd engine
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
python portfolio/holdings.py  # init DB
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### 4. FastAPI (optional — faster responses)

```bash
cd engine
.venv\Scripts\activate
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend auto-detects FastAPI at `localhost:8000` and falls back to subprocess if unavailable.

## Pages

| Page | Description |
|---|---|
| **Dashboard** | Portfolio value, P&L, risk metrics, benchmark comparison, top positions, AI summary |
| **Holdings** | Add/delete holdings, live positions with P&L, ↺ Refresh Data (price + history) |
| **Performance** | Equity curve, period selector (1M–2Y), return/risk breakdown |
| **Allocation** | Asset/type pie charts, sector weights (ETF-weighted), ETF holdings breakdown |
| **Optimizer** | 5 models side-by-side comparison, weights bar chart, rebalance plan |
| **News** | Latest news filtered by symbol, cached once per day per symbol |

## Optimizer Models

| Model | Description |
|---|---|
| Max Sharpe | Maximize risk-adjusted return |
| HRP | Hierarchical Risk Parity — cluster-based diversification |
| Min Volatility | Minimize portfolio variance |
| Risk Parity | Equal risk contribution per asset |
| Equal Weight | Simple 1/N allocation |

## Data Flow

```
User adds holding (ETF)
  → POST /api/holdings
  → cli.py holdings --action add --exchange arcx
  → DB: holdings table
  → fire-and-forget: cli.py morningstar --symbol VT --exchange arcx
    → Playwright scrapes Morningstar
    → DB: etf_holdings + etf_allocation tables

Holdings → ↺ Refresh Data
  → POST /api/prices/refresh
  → cli.py refresh
  → force-clear price cache for holding symbols
  → fetch current prices (CoinGecko / yfinance)
  → incremental history fetch (new dates only)
  → DB: prices + price_history tables
```

## Config

Key settings in `config.yaml`:

```yaml
portfolio:
  benchmark: SPY          # benchmark for alpha/beta

optimizer:
  lookback_days: 365
  risk_free_rate: 0.03
  rebalance_threshold: 0.10

refresh:
  price_interval_seconds: 300   # price cache TTL

ai:
  model: gemini-3-flash-preview
  language: th
```

## Database Tables

| Table | Description |
|---|---|
| `holdings` | User's portfolio positions (symbol, qty, cost, exchange) |
| `prices` | Current price cache (5-min TTL) |
| `price_history` | Daily OHLC for metrics + optimizer |
| `etf_holdings` | Top 10 holdings per ETF (from Morningstar) |
| `etf_allocation` | Sector + region weights per ETF |
| `ai_summary` | Daily AI summary cache |
| `news_cache` | News articles cached per symbol per day |
| `asset_info` | Sector/industry/country from yfinance |
