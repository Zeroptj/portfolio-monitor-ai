"""
morningstar.py — ดึงข้อมูล ETF จาก Morningstar แล้ว save ลง DB

Tables ที่เขียน:
  etf_holdings   → top 10 holdings ของแต่ละ ETF
  etf_allocation → sector/region allocation

Exchange ของแต่ละ ETF อ่านจาก config.yaml (assets.etf[].exchange)
เรียกจาก scheduler ทุกเดือน
"""

import os
import sys
import time
import yaml
from datetime import datetime

from playwright.sync_api import sync_playwright

ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR   = os.path.dirname(ENGINE_DIR)
sys.path.insert(0, ENGINE_DIR)

from portfolio.holdings import SessionLocal, ETFHolding, ETFAllocation, init_db

with open(os.path.join(ENGINE_DIR, "config.yaml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

DEFAULT_EXCHANGE = "arcx"


# ─── Config Helper ───────────────────────────────────────────────────────────

def _get_exchange(ticker: str) -> str:
    """อ่าน exchange จาก config.yaml assets.etf[].exchange (fallback arcx)"""
    for etf in config["assets"].get("etf", []):
        if etf["symbol"] == ticker:
            return etf.get("exchange", DEFAULT_EXCHANGE)
    return DEFAULT_EXCHANGE


# ─── Page Utilities ──────────────────────────────────────────────────────────

def _wait_ready(page, timeout: int = 30_000):
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
        page.wait_for_load_state("domcontentloaded", timeout=timeout)
        time.sleep(2)
    except Exception:
        pass


def _close_popups(page):
    selectors = [
        'button[aria-label="Close"]',
        'button[aria-label*="close" i]',
        'button.mdc-dialog__close',
        'button:has-text("Accept")',
        'button:has-text("I Accept")',
    ]
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                page.locator(sel).first.click(timeout=2000)
                time.sleep(0.5)
                return
        except Exception:
            continue


def _new_browser_context(playwright):
    browser = playwright.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
    )
    return browser, context


# ─── Scrapers ────────────────────────────────────────────────────────────────

def _scrape_top10(page) -> list[dict]:
    """Top 10 holdings จาก Quote page"""
    print("  [morningstar] Scraping top 10 holdings...")
    try:
        rows = page.locator("div.mdc-fund-top-holdings__table__mdc table tbody tr")
        rows.first.wait_for(timeout=15_000)
        results = []
        for i in range(rows.count()):
            row = rows.nth(i)
            try:
                name   = row.locator("td:nth-child(1) h3").inner_text().strip()
                weight = row.locator("td:nth-child(2) span").inner_text().strip()
                results.append({"name": name, "weight_pct": float(weight)})
            except Exception:
                continue
        print(f"  [morningstar] Found {len(results)} holdings")
        return results
    except Exception as e:
        print(f"  [morningstar] top10 error: {e}")
        return []


def _scrape_sector(page) -> list[dict]:
    """Sector exposure จาก Portfolio page"""
    print("  [morningstar] Scraping sector exposure...")
    try:
        page.wait_for_selector("table.sal-sector-exposure__sector-table", timeout=10_000)
        rows = page.locator("table.sal-sector-exposure__sector-table tbody tr").all()
        results = []
        for row in rows:
            try:
                name   = row.locator("th span").last.inner_text().strip()
                cells  = row.locator("td").all()
                weight = cells[0].inner_text().strip() if cells else "0"
                if name:
                    results.append({"name": name, "weight": weight})
            except Exception:
                continue
        print(f"  [morningstar] Found {len(results)} sectors")
        return results
    except Exception as e:
        print(f"  [morningstar] sector error: {e}")
        return []


def _scrape_region(page) -> list[dict]:
    """Region exposure จาก Portfolio page (คลิก Region tab ก่อน)"""
    print("  [morningstar] Scraping region exposure...")
    try:
        region_btn = None
        for sel in [
            'button#region',
            'button[role="tab"]:has-text("Region")',
            'button.mds-button-group__item__sal:has-text("Region")',
        ]:
            if page.locator(sel).count() > 0:
                region_btn = page.locator(sel).first
                break

        if region_btn and region_btn.get_attribute("aria-selected") != "true":
            region_btn.click(timeout=10_000)
            time.sleep(2)

        page.wait_for_selector("table.sal-region-exposure__region-table", timeout=10_000)
        rows = page.locator("table.sal-region-exposure__region-table tbody tr").all()
        results = []
        for row in rows:
            try:
                name   = row.locator("th span").inner_text().strip()
                cells  = row.locator("td").all()
                weight = cells[0].inner_text().strip() if cells else "0"
                if name:
                    results.append({"name": name, "weight": weight})
            except Exception:
                continue
        print(f"  [morningstar] Found {len(results)} regions")
        return results
    except Exception as e:
        print(f"  [morningstar] region error: {e}")
        return []


# ─── Save to DB ──────────────────────────────────────────────────────────────

def _save_holdings(etf: str, holdings: list[dict]):
    """Replace etf_holdings rows สำหรับ ETF นี้"""
    db = SessionLocal()
    try:
        db.query(ETFHolding).filter(ETFHolding.etf == etf).delete()
        now = datetime.now()
        for h in holdings:
            db.add(ETFHolding(
                etf        = etf,
                symbol     = None,   # Morningstar top10 ไม่ให้ ticker
                name       = h["name"],
                weight     = h["weight_pct"],
                updated_at = now,
            ))
        db.commit()
        print(f"  [morningstar] Saved {len(holdings)} holdings for {etf}")
    except Exception as e:
        db.rollback()
        print(f"  [morningstar] DB error (holdings): {e}")
    finally:
        db.close()


def _save_allocation(etf: str, alloc_type: str, rows: list[dict]):
    """Replace etf_allocation rows สำหรับ ETF + type นี้"""
    db = SessionLocal()
    try:
        db.query(ETFAllocation).filter(
            ETFAllocation.etf  == etf,
            ETFAllocation.type == alloc_type,
        ).delete()
        now = datetime.now()
        for row in rows:
            try:
                weight = float(
                    row["weight"].replace("%", "").replace("–", "0").replace("-", "0") or "0"
                )
            except Exception:
                weight = 0.0
            db.add(ETFAllocation(
                etf        = etf,
                type       = alloc_type,
                name       = row["name"],
                weight     = weight,
                updated_at = now,
            ))
        db.commit()
        print(f"  [morningstar] Saved {len(rows)} {alloc_type} rows for {etf}")
    except Exception as e:
        db.rollback()
        print(f"  [morningstar] DB error (allocation/{alloc_type}): {e}")
    finally:
        db.close()


# ─── Allocation Type Detection ───────────────────────────────────────────────

_BOND_SECTOR_NAMES = {
    "government", "municipal", "corporate", "securitized",
    "cash & equivalents", "derivative",
}

def _resolve_alloc_type(sectors: list[dict]) -> str:
    """
    ตรวจว่า sector data ที่ scrape มาเป็น equity sectors หรือ fixed income categories
    Morningstar ใช้ตารางเดียวกันสำหรับ bond ETF → ชื่อจะเป็น Government/Corporate ฯลฯ
    """
    names = {s["name"].lower() for s in sectors}
    if names & _BOND_SECTOR_NAMES:
        return "exposure"
    return "sector"


# ─── Per-ETF Scraper ─────────────────────────────────────────────────────────

def scrape_etf(ticker: str, exchange: str, max_retries: int = 3) -> bool:
    """
    Scrape + save ข้อมูลสำหรับ ETF เดียว
    Returns True ถ้าสำเร็จ
    """
    base          = f"https://www.morningstar.com/etfs/{exchange.lower()}/{ticker.lower()}"
    quote_url     = f"{base}/quote"
    portfolio_url = f"{base}/portfolio"

    for attempt in range(1, max_retries + 1):
        print(f"\n[morningstar] {ticker} — attempt {attempt}/{max_retries}")
        try:
            with sync_playwright() as pw:
                browser, ctx = _new_browser_context(pw)
                page = ctx.new_page()

                page.goto(quote_url, wait_until="domcontentloaded", timeout=60_000)
                _wait_ready(page)
                _close_popups(page)
                holdings = _scrape_top10(page)

                page.goto(portfolio_url, wait_until="domcontentloaded", timeout=60_000)
                _wait_ready(page)
                _close_popups(page)
                sectors = _scrape_sector(page)
                regions = _scrape_region(page)

                browser.close()

            if not holdings and not sectors and not regions:
                raise ValueError("All sections returned empty")

            if holdings:
                _save_holdings(ticker, holdings)
            if sectors:
                alloc_type = _resolve_alloc_type(sectors)
                _save_allocation(ticker, alloc_type, sectors)
            if regions:
                _save_allocation(ticker, "region", regions)

            return True

        except Exception as e:
            print(f"[morningstar] {ticker} attempt {attempt} failed: {e}")
            if attempt < max_retries:
                time.sleep(attempt * 5)

    print(f"[morningstar] {ticker} — all retries exhausted")
    return False


# ─── Public Job ──────────────────────────────────────────────────────────────

def refresh_etf_data() -> dict[str, bool]:
    """
    Scrape + save ETF data สำหรับทุก ETF ใน config
    เรียกจาก scheduler ทุกเดือน
    Returns {ticker: success_bool}
    """
    etfs = config["assets"].get("etf", [])
    results: dict[str, bool] = {}

    print(f"[morningstar] Refreshing {len(etfs)} ETFs...")

    for i, etf in enumerate(etfs):
        ticker = etf["symbol"]
        ok     = scrape_etf(ticker, _get_exchange(ticker))
        results[ticker] = ok

        if i < len(etfs) - 1:
            time.sleep(10)

    success = sum(results.values())
    print(f"\n[morningstar] Done — {success}/{len(etfs)} succeeded")
    return results


# ─── CLI test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    test_ticker = "SPY"
    print(f"Testing get_etf_holdings: {test_ticker}")
    holdings = get_etf_holdings(test_ticker)

    print(f"\nTop holdings ({test_ticker}):")
    for h in holdings:
        print(f"  {h['name']:35s} {h['weight_pct']:.2f}%")

    sectors = get_etf_allocation(test_ticker, "sector")
    print(f"\nSector allocation ({test_ticker}):")
    for s in sectors:
        print(f"  {s['name']:30s} {s['weight']:.2f}%")

    print("\nSecond call (should be from DB, no scraping):")
    holdings2 = get_etf_holdings(test_ticker)
    print(f"  Got {len(holdings2)} holdings from cache")
