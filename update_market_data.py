#!/usr/bin/env python3
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

THAI_TZ = timezone(timedelta(hours=7))

THAI_STOCKS = [
    "PTT", "DELTA", "CPALL", "AOT", "BDMS", "SCB", "KBANK",
    "ADVANC", "GULF", "TRUE", "KTB", "HANA", "SCC", "PTTGC",
    "OR", "MINT", "CPF"
]

US_STOCKS = [
    "AAPL", "TSLA", "NVDA", "VOO", "QQQ", "MSFT", "GOOGL",
    "AMZN", "SPY", "META"
]

CRYPTO_SYMBOLS = [
    "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "DOT", "LINK", "AVAX"
]

def fetch_json(url: str, timeout: int = 8):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FinTrackBot/1.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_usd_thb() -> float:
    try:
        data = fetch_json("https://open.er-api.com/v6/latest/USD")
        rate = float(data.get("rates", {}).get("THB", 34.50))
        return round(rate, 2) if 25.0 < rate < 50.0 else 34.50
    except Exception as e:
        return 34.50

def fetch_thai_gold() -> dict:
    try:
        data = fetch_json("https://api.chnwt.dev/thai-gold-api/latest")
        resp = data.get("response", {})
        price = resp.get("price", {})
        bar = price.get("gold_bar", {})
        ornament = price.get("gold", {})

        def parse_num(val, default):
            if not val:
                return default
            return float(str(val).replace(",", "").strip())

        return {
            "bar_buy": parse_num(bar.get("buy"), 68350.0),
            "bar_sell": parse_num(bar.get("sell"), 68550.0),
            "ornament_buy": parse_num(ornament.get("buy"), 66976.88),
            "ornament_sell": parse_num(ornament.get("sell"), 69350.0),
            "update_date": resp.get("update_date", ""),
            "update_time": resp.get("update_time", "18:00 น."),
        }
    except Exception as e:
        return {
            "bar_buy": 68350.0,
            "bar_sell": 68550.0,
            "ornament_buy": 66976.88,
            "ornament_sell": 69350.0,
            "update_date": datetime.now(THAI_TZ).strftime("%d/%m/%Y"),
            "update_time": "18:00 น.",
        }

def fetch_yahoo_quote(yahoo_symbol: str) -> dict | None:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?interval=1d&range=1d"
        data = fetch_json(url)
        results = data.get("chart", {}).get("result", [])
        if not results:
            return None
        meta = results[0].get("meta", {})
        price = float(meta.get("regularMarketPrice", 0.0))
        prev = float(meta.get("chartPreviousClose", price))
        if price <= 0:
            return None
        change_pct = round(((price - prev) / prev) * 100.0, 2) if prev > 0 else 0.0
        name = meta.get("longName") or meta.get("shortName") or yahoo_symbol
        return {
            "price": round(price, 2),
            "prev_close": round(prev, 2),
            "change_pct": change_pct,
            "name": name,
        }
    except Exception as e:
        return None

def fetch_crypto_batch(usd_thb: float) -> dict:
    result = {
        "USDT": {"price_usd": 1.0, "change_pct": 0.0},
        "USDC": {"price_usd": 1.0, "change_pct": 0.0}
    }
    try:
        bitkub_data = fetch_json("https://api.bitkub.com/api/market/ticker")
        for sym in CRYPTO_SYMBOLS:
            pair_key = f"THB_{sym}"
            if pair_key in bitkub_data:
                coin_obj = bitkub_data[pair_key]
                last_thb = float(coin_obj.get("last", 0.0))
                change_pct = round(float(coin_obj.get("percentChange", 0.0)), 2)
                if last_thb > 0 and usd_thb > 0:
                    result[sym] = {
                        "price_usd": round(last_thb / usd_thb, 2),
                        "price_thb": round(last_thb, 2),
                        "change_pct": change_pct
                    }
    except Exception as e:
        pass

    missing = [s for s in CRYPTO_SYMBOLS if s not in result]
    for sym in missing:
        try:
            url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={sym}USDT"
            item = fetch_json(url)
            price_usd = float(item.get("lastPrice", 0.0))
            change_pct = round(float(item.get("priceChangePercent", 0.0)), 2)
            if price_usd > 0:
                result[sym] = {
                    "price_usd": price_usd,
                    "price_thb": round(price_usd * usd_thb, 2),
                    "change_pct": change_pct,
                }
        except Exception as e:
            pass
    return result

def main():
    now_th = datetime.now(THAI_TZ)
    usd_thb = fetch_usd_thb()
    gold = fetch_thai_gold()

    thai_stocks_map = {}
    for sym in THAI_STOCKS:
        q = fetch_yahoo_quote(f"{sym}.BK")
        if q:
            thai_stocks_map[sym] = q

    us_stocks_map = {}
    for sym in US_STOCKS:
        q = fetch_yahoo_quote(sym)
        if q:
            us_stocks_map[sym] = {
                "price_usd": q["price"],
                "change_pct": q["change_pct"],
                "name": q["name"],
            }

    crypto_map = fetch_crypto_batch(usd_thb)

    payload = {
        "timestamp": int(time.time() * 1000),
        "updated_at": now_th.isoformat(),
        "usd_thb": usd_thb,
        "gold": gold,
        "thai_stocks": thai_stocks_map,
        "us_stocks": us_stocks_map,
        "crypto": crypto_map,
    }

    with open("market_data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("Generated market_data.json successfully")

if __name__ == "__main__":
    main()
