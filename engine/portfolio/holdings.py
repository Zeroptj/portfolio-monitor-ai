import os
import yaml
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer,
    String, Float, DateTime, Text, text
)
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()


with open("../config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# สร้าง database — DATABASE_URL env var ใช้ตอน deploy (Fly.io volume: sqlite:////data/portfolio.db)
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_default  = f"sqlite:///{os.path.join(BASE_DIR, '../data/portfolio.db')}"
_db_url   = os.getenv("DATABASE_URL", _default)
engine    = create_engine(_db_url)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def _run_migrations():
    """Run lightweight column-add migrations on startup"""
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE holdings ADD COLUMN exchange VARCHAR"))
            conn.commit()
    except Exception:
        pass  # column already exists or table not yet created

_run_migrations()


# ตาราง holdings (user data)
class Holding(Base):
    __tablename__ = "holdings"
    id          = Column(Integer, primary_key=True)
    symbol      = Column(String, nullable=False)
    name        = Column(String)
    asset_type  = Column(String)   # crypto/stock/etf/commodity
    exchange    = Column(String, nullable=True)  # exchange สำหรับ ETF เช่น arcx
    quantity    = Column(Float, nullable=False)
    cost        = Column(Float, nullable=False)  # ต้นทุนต่อหน่วย
    created_at  = Column(DateTime, default=datetime.now)
    updated_at  = Column(DateTime, default=datetime.now)

# ตาราง prices (cache ราคาล่าสุด)
class Price(Base):
    __tablename__ = "prices"
    id          = Column(Integer, primary_key=True)
    symbol      = Column(String, nullable=False)
    price       = Column(Float)
    currency    = Column(String, default="USD")
    updated_at  = Column(DateTime, default=datetime.now)

# ตาราง price_history (สำหรับ chart + optimizer)
class PriceHistory(Base):
    __tablename__ = "price_history"
    id          = Column(Integer, primary_key=True)
    symbol      = Column(String, nullable=False)
    date        = Column(String, nullable=False)  # YYYY-MM-DD
    close       = Column(Float)
    updated_at  = Column(DateTime, default=datetime.now)

# ตาราง asset_info (sector/region จาก yfinance)
class AssetInfo(Base):
    __tablename__ = "asset_info"
    id          = Column(Integer, primary_key=True)
    symbol      = Column(String, nullable=False)
    asset_type  = Column(String)
    sector      = Column(String)
    industry    = Column(String)
    country     = Column(String)
    updated_at  = Column(DateTime, default=datetime.now)

# ตาราง etf_holdings (จาก morningstar)
class ETFHolding(Base):
    __tablename__ = "etf_holdings"
    id          = Column(Integer, primary_key=True)
    etf         = Column(String, nullable=False)
    symbol      = Column(String)
    name        = Column(String)
    weight      = Column(Float)
    updated_at  = Column(DateTime, default=datetime.now)

# ตาราง etf_allocation (sector/region จาก morningstar)
class ETFAllocation(Base):
    __tablename__ = "etf_allocation"
    id          = Column(Integer, primary_key=True)
    etf         = Column(String, nullable=False)
    type        = Column(String)   # sector หรือ region
    name        = Column(String)
    weight      = Column(Float)
    updated_at  = Column(DateTime, default=datetime.now)

# ตาราง ai_summary (เก็บประวัติ)
class AISummary(Base):
    __tablename__ = "ai_summary"
    id          = Column(Integer, primary_key=True)
    date        = Column(String, nullable=False)  # YYYY-MM-DD
    summary     = Column(Text)
    created_at  = Column(DateTime, default=datetime.now)

# ตาราง news_cache (cache รายวันต่อ symbol)
class NewsCache(Base):
    __tablename__ = "news_cache"
    id          = Column(Integer, primary_key=True)
    date        = Column(String, nullable=False)   # YYYY-MM-DD
    symbol      = Column(String, nullable=False)   # "" = general
    title       = Column(String)
    description = Column(Text)
    url         = Column(String)
    source      = Column(String)
    published_at= Column(String)
    created_at  = Column(DateTime, default=datetime.now)


# สร้างตารางทั้งหมด + migration
def init_db():
    Base.metadata.create_all(engine)
    # migration: add exchange column if missing (existing DB)
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE holdings ADD COLUMN exchange VARCHAR"))
            conn.commit()
    except Exception:
        pass  # column already exists
    print("Database initialized")

# ── Holdings CRUD ──────────────────────────

def get_holdings():
    db = SessionLocal()
    try:
        return db.query(Holding).all()
    finally:
        db.close()

def add_holding(symbol, name, asset_type, quantity, cost, exchange=None):
    db = SessionLocal()
    try:
        holding = Holding(
            symbol     = symbol.upper(),
            name       = name,
            asset_type = asset_type,
            exchange   = exchange or (None if asset_type != "etf" else "arcx"),
            quantity   = quantity,
            cost       = cost
        )
        db.add(holding)
        db.commit()
        db.refresh(holding)   # โหลด id/attributes ก่อนปิด session
        return holding
    finally:
        db.close()

def update_holding(id, quantity=None, cost=None):
    db = SessionLocal()
    try:
        holding = db.query(Holding).filter(Holding.id == id).first()
        if quantity: holding.quantity = quantity
        if cost:     holding.cost = cost
        holding.updated_at = datetime.now()
        db.commit()
        db.refresh(holding)   # โหลด attributes ก่อนปิด session
        return holding
    finally:
        db.close()

def delete_holding(id):
    db = SessionLocal()
    try:
        holding = db.query(Holding).filter(Holding.id == id).first()
        db.delete(holding)
        db.commit()
        return True
    finally:
        db.close()

def get_current_weights(current_prices: dict):
    """คำนวณ % น้ำหนักแต่ละ asset จากราคาปัจจุบัน"""
    db = SessionLocal()
    try:
        holdings = db.query(Holding).all()
        values = {
            h.symbol: h.quantity * current_prices.get(h.symbol, 0)
            for h in holdings
        }
        total = sum(values.values())
        if total == 0:
            return {}
        return {symbol: (value / total) * 100 
                for symbol, value in values.items()}
    finally:
        db.close()


if __name__ == "__main__":
    init_db()