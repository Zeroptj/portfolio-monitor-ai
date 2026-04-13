# Portfolio Monitor AI

Personal portfolio monitoring tool with optional AI analysis. Bloomberg-style dark UI built with Next.js + Python FastAPI.

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript |
| Backend | FastAPI + Uvicorn (Python 3.13) |
| Database | SQLite via SQLAlchemy |
| AI (optional) | Groq — `llama-3.1-8b-instant` |
| Prices | CoinGecko (crypto), yfinance (stocks/ETF) |
| ETF Data | Morningstar (holdings, sector, region via Playwright) |
| News | NewsAPI |
| Optimizer | PyPortfolioOpt + Riskfolio-Lib |

---

## Project Structure

```
portfolio-monitor-ai/
├── .env                     # API keys (not committed)
├── .env.example             # Template
├── config.yaml              # Assets, benchmark, refresh intervals, AI config
├── engine/
│   ├── requirements.txt
│   ├── main.py              # FastAPI server
│   ├── scheduler.py         # Background jobs (prices, news, AI summary, ETF)
│   ├── cli.py               # CLI entry point (subprocess fallback)
│   ├── ai/
│   │   ├── summary.py       # Daily AI portfolio summary
│   │   └── recommender.py   # AI allocation insight + optimizer advice
│   ├── data/
│   │   ├── price_feed.py    # CoinGecko + yfinance price fetching + history
│   │   ├── morningstar.py   # ETF holdings/sector/region scraper
│   │   └── news_feed.py     # NewsAPI with daily DB cache
│   └── portfolio/
│       ├── holdings.py      # SQLAlchemy models + CRUD + DB init
│       ├── metrics.py       # Sharpe, drawdown, alpha, beta, volatility
│       └── optimizer.py     # 5 optimization models + rebalance plan
└── frontend/
    ├── app/                 # Next.js App Router pages
    │   ├── dashboard/       # Overview, metrics, benchmark, AI summary
    │   ├── holdings/        # Add/delete holdings, live P&L table
    │   ├── performance/     # Equity curve, period selector, benchmark comparison
    │   ├── allocation/      # Asset type, sector, fixed income exposure, region
    │   ├── optimizer/       # 5-model comparison, weights, rebalance plan
    │   └── news/            # News filtered by holding symbol
    ├── components/
    │   ├── charts/          # EquityCurve, AllocationPie, BarComparison
    │   ├── layout/          # Sidebar
    │   └── portfolio/       # MetricCard, HoldingsTable, AIBox, RebalanceTable
    ├── lib/
    │   ├── api.ts           # All API calls (axios → /api/*)
    │   ├── python.ts        # FastAPI-first, subprocess fallback
    │   └── ai-context.tsx   # React context for AI feature flag
    └── types/
        └── portfolio.ts     # TypeScript interfaces
```

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11+ (tested on 3.13.2) |
| Node.js | 18+ (tested on 22.14.0) |
| npm | 8+ (tested on 10.9.2) |

---

## Setup

### 1. Clone and configure environment

```bash
git clone <repo-url>
cd portfolio-monitor-ai

cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
# Required for news feed
NEWS_API_KEY=your_newsapi_key_here

# Required for AI features (leave empty to run without AI)
GROQ_API_KEY=your_groq_key_here
```

- **NewsAPI**: free key at [newsapi.org](https://newsapi.org)
- **Groq**: free key at [console.groq.com](https://console.groq.com)  
  If `GROQ_API_KEY` is empty, the app runs normally without any AI features.

---

### 2. Python — create venv and install dependencies

```bash
cd engine

# Create virtual environment
python -m venv .venv

# Activate
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Install Playwright browsers (required for ETF scraping)

```bash
playwright install chromium
```

> Only needed if you plan to add ETF holdings. Stocks and crypto work without it.

---

### 3. Initialize the database

```bash
# Still inside engine/ with venv active
python portfolio/holdings.py
```

This creates `engine/data/portfolio.db` with all required tables:

| Table | Contents |
|---|---|
| `holdings` | Your portfolio positions |
| `prices` | Current price cache |
| `price_history` | Daily price history for metrics + optimizer |
| `etf_holdings` | Top holdings per ETF (from Morningstar) |
| `etf_allocation` | Sector, exposure, region weights per ETF |
| `ai_summary` | Daily AI summary cache |
| `news_cache` | News articles per symbol per day |

---

### 4. Start the backend (FastAPI)

```bash
# Inside engine/ with venv active
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Expected output:

```
[startup] AI features: ENABLED        ← or DISABLED if no key
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Verify it works:

```bash
curl http://127.0.0.1:8000/health
# → {"status":"ok"}

curl http://127.0.0.1:8000/ai/status
# → {"enabled":true}   or   {"enabled":false}
```

---

### 5. Start the frontend

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

> The frontend auto-detects FastAPI at `localhost:8000` and falls back to Python subprocess if unavailable. FastAPI mode is significantly faster.

---

### 6. (Optional) Start the background scheduler

Open a third terminal:

```bash
cd engine
.venv\Scripts\activate   # or source .venv/bin/activate
python scheduler.py
```

Jobs:

| Job | Schedule | Description |
|---|---|---|
| `prices` | Every 5 min (configurable) | Refresh current prices for all holdings |
| `news` | Daily 08:00 | Fetch news for general market + holdings |
| `ai_summary` | Daily 08:10 | Regenerate AI portfolio summary (skipped if AI disabled) |
| `etf_data` | 1st of month, 02:00 | Re-scrape Morningstar ETF data |

---

## Running without AI

If you don't have a Groq API key (or want to disable AI):

1. Leave `GROQ_API_KEY` empty in `.env`  
   **or** set `AI_ENABLED=false`

The app runs fully without AI. The backend skips AI route registration and the frontend automatically hides all AI buttons and summary boxes.

To re-enable later, add the key and restart the backend.

---

## Usage Guide

### Adding your first holding

1. Go to **Holdings** → click **+ ADD**
2. Fill in symbol (e.g. `AAPL`), quantity, average cost
3. Select asset type: `stock`, `etf`, `crypto`, `commodity`, or `other`
4. For ETF: enter the exchange code (default `arcx` for NYSE Arca, `xnas` for Nasdaq, `xnys` for NYSE)
5. Click **↺ REFRESH DATA** to fetch current prices and 1-year history

### ETF allocation data

After adding an ETF holding, the app automatically fetches sector/region data from Morningstar in the background. This may take 10–30 seconds. The Allocation page will show sector weights once done.

### Running the optimizer

1. Go to **Optimizer** → click **RUN OPTIMIZER**
2. All 5 models run in parallel (~10–30s depending on history data)
3. Click any model row to view its target weights and rebalance plan
4. If AI is enabled, an AI analysis appears automatically after the run

### Fetching price history

Price history is required for Performance charts and the Optimizer. After adding holdings:

```bash
# Manual fetch via CLI
cd engine
.venv\Scripts\activate
python cli.py history
```

Or click **↺ REFRESH DATA** on the Holdings page.

---

## Configuration

Key settings in `config.yaml`:

```yaml
portfolio:
  benchmark: SPY              # benchmark symbol for alpha/beta/correlation

optimizer:
  lookback_days: 1100         # days of history used for optimization
  risk_free_rate: 0.03        # annual risk-free rate (3%)
  rebalance_threshold: 0.10   # drift threshold to trigger rebalance alert (10%)

refresh:
  price_interval_seconds: 300 # scheduler price refresh interval
  ai_summary_time: "08:00"    # daily AI summary time (HH:MM)
  timezone: "Asia/Bangkok"

ai:
  model: llama-3.1-8b-instant
  max_tokens: 500
```

---

## Pages

| Page | Description |
|---|---|
| **Dashboard** | Total value, P&L, Sharpe, drawdown, benchmark comparison, AI daily summary |
| **Holdings** | Add/delete positions, live P&L table, data refresh |
| **Performance** | Equity curve (1M / 3M / 6M / 1Y / 2Y), return and risk metrics |
| **Allocation** | Asset type breakdown, sector weights, fixed income exposure, region weights |
| **Optimizer** | 5-model comparison table, target weights bar chart, rebalance action plan |
| **News** | Market news filtered by symbol, cached once per day |

---

## Optimizer Models

| Model | Description |
|---|---|
| **Max Sharpe** | Maximize risk-adjusted return |
| **HRP** | Hierarchical Risk Parity — cluster-based diversification |
| **Min Volatility** | Minimize portfolio variance |
| **Risk Parity** | Equal risk contribution per asset |
| **Equal Weight** | Simple 1/N allocation baseline |

---

## Troubleshooting

**`ModuleNotFoundError` on startup**  
Make sure venv is activated before running any Python command.

**Optimizer returns no results / errors**  
Price history may be missing. Run `python cli.py history` or click Refresh Data, then wait for the download to complete.

**ETF sector data not showing**  
Playwright may not be installed. Run `playwright install chromium` with the venv active.

**AI features not working despite having a key**  
Check `curl http://127.0.0.1:8000/ai/status`. If `"enabled": false`, verify that `GROQ_API_KEY` is set in `.env` at the project root (not inside `engine/`).

**News always empty**  
`NEWS_API_KEY` is required. Free tier at [newsapi.org](https://newsapi.org). Also note that the free tier only allows queries for articles published within the last 24 hours.
