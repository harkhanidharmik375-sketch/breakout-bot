import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import io
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=12)
    except Exception as e:
        print("Telegram error:", e)

# 1. Broad Market Watchlist
def get_universe():
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(r.text))
        return [f"{sym}.NS" for sym in df['Symbol'].dropna().tolist()]
    except:
        return [
            "INDUSINDBK.NS", "SGFIN.NS", "SGMART.NS", "CUB.NS", "RAYMOND.NS",
            "CUPID.NS", "VOLTAS.NS", "TATATECH.NS", "LAURUSLABS.NS", "TECHM.NS",
            "HDFCBANK.NS", "IREDA.NS", "DIXON.NS", "KAYNES.NS", "E2E.NS", "WABAG.NS"
        ]

# 2. Sectoral Flow Engine (Finds where money is entering)
SECTOR_MAP = {
    "^NSEI": "NIFTY 50",
    "^NSEBANK": "BANKING",
    "^CNXIT": "IT & TECH",
    "^CNXAUTO": "AUTO",
    "^CNXFMCG": "FMCG",
    "^CNXMETAL": "METALS",
    "^CNXREALTY": "REALTY",
    "^CNXPHARMA": "PHARMA",
    "^CNXINFRA": "INFRASTRUCTURE"
}

def get_sector_momentum():
    sector_perf = {}
    try:
        data = yf.download(tickers=list(SECTOR_MAP.keys()), period="5d", interval="1d", progress=False)
        for sym, name in SECTOR_MAP.items():
            closes = data['Close'][sym].dropna()
            if len(closes) >= 2:
                pct = ((closes.iloc[-1] - closes.iloc[-2]) / closes.iloc[-2]) * 100
                sector_perf[name] = round(pct, 2)
    except Exception as e:
        print(f"Sector fetch error: {e}")
    sorted_sectors = sorted(sector_perf.items(), key=lambda x: x[1], reverse=True)
    return sorted_sectors

# 3. Main Multi-Agent Screener
def run_market_lab():
    stocks = get_universe()
    sectors = get_sector_momentum()
    
    top_sector_name = sectors[0][0] if sectors else "BROAD MARKET"
    top_sector_gain = sectors[0][1] if sectors else 0.0
    
    print(f"Top Sector Today: {top_sector_name} (+{top_sector_gain}%)")
    print(f"Scanning {len(stocks)} stocks...")

    try:
        data = yf.download(tickers=stocks, period="60d", interval="1d", group_by="ticker", threads=True, timeout=40)
    except Exception as e:
        print(f"Download Error: {e}")
        return

    candidates = []

    for sym in stocks:
        try:
            df = data[sym].dropna() if len(stocks) > 1 else data.dropna()
            if len(df) < 40:
                continue

            c = df.iloc[-1]
            prev = df.iloc[:-1]

            close = float(c['Close'])
            high = float(c['High'])
            low = float(c['Low'])
            open_p = float(c['Open'])
            volume = float(c['Volume'])

            # Historical Metrics
            h20 = float(prev['High'].tail(20).max())
            h52w = float(prev['High'].tail(52*5).max()) if len(prev) >= 100 else h20
            v_avg20 = float(prev['Volume'].tail(20).mean())
            turnover = close * volume

            # Moving Averages
            ema9 = float(df['Close'].ewm(span=9).mean().iloc[-1])
            ema21 = float(df['Close'].ewm(span=21).mean().iloc[-1])
            ema50 = float(df['Close'].ewm(span=50).mean().iloc[-1])

            # VCP & Range Calculations
            candle_range = high - low
            upper_wick = high - close
            clean_wick = (upper_wick <= candle_range * 0.16) if candle_range > 0 else False
            dist_52w = round(((h52w - close) / h52w) * 100, 1)

            # INSTITUTIONAL 100-POINT SCORING SYSTEM
            score = 0
            reasons = []

            # 1. Base Breakout (25 Pts)
            if close > h20:
                score += 25
                reasons.append("Multi-Day Resistance Cleared")

            # 2. Blue Sky / 52W Proximity (20 Pts)
            if dist_52w <= 8.0:
                score += 20
                reasons.append(f"Near 52W High ({dist_52w}% away)")
            elif dist_52w <= 15.0:
                score += 10
                reasons.append(f"Within 15% of 52W High")

            # 3. Institutional Volume Shock (20 Pts)
            vol_multiplier = round(volume / v_avg20, 1) if v_avg20 > 0 else 1.0
            if vol_multiplier >= 2.5:
                score += 20
                reasons.append(f"Aggressive Volume Shock ({vol_multiplier}x)")
            elif vol_multiplier >= 1.5:
                score += 10
                reasons.append(f"Solid Volume Expansion ({vol_multiplier}x)")

            # 4. Stage-2 Trend Alignment (15 Pts)
            if ema9 > ema21 and ema21 > ema50 and close > ema9:
                score += 15
                reasons.append("Stage-2 Trend Aligned (9>21>50)")

            # 5. Clean Institutional Bar (10 Pts)
            if clean_wick and close > open_p:
                score += 10
                reasons.append("Zero Upper Wick (Buyers in Total Control)")

            # 6. High Cash Flow / Liquidity (10 Pts)
            if turnover >= 100000000: # 10 Cr+
                score += 10
                reasons.append(f"Heavy Institutional Cash Flow (₹{round(turnover/10000000, 1)} Cr)")

            # TRIGGER ONLY HIGH-CONVICTION STOCKS (Score >= 80)
            if score >= 80 and turnover >= 60000000 and (close >= open_p * 1.015):
                # Target & SL Calculations
                sl_price = round(max(low, close * 0.965), 2)
                t1_price = round(close * 1.05, 2)  # +5% Quick
                t2_price = round(close * 1.15, 2) # +15% Swing
                t3_price = round(close * 1.30, 2) # +30% Multibagger Runway
                risk_pct = round(((close - sl_price) / close) * 100, 1)

                dossier = {
                    "symbol": sym.replace(".NS", ""),
                    "score": score,
                    "close": round(close, 2),
                    "sl": sl_price,
                    "risk": risk_pct,
                    "t1": t1_price,
                    "t2": t2_price,
                    "t3": t3_price,
                    "vol_x": vol_multiplier,
                    "turnover_cr": round(turnover / 10000000, 1),
                    "reasons": reasons
                }
                candidates.append(dossier)

        except Exception as e:
            continue

    # Sort by Highest Institutional Score
    candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)

    if candidates:
        top_picks = candidates[:2] # Best 1 or 2 Gems
        for p in top_picks:
            reasons_bullet = "\n• " + "\n• ".join(p['reasons'])
            alert_text = (
                f"⛏️ *MARKET LAB: INSTITUTIONAL DOSSIER* 💎\n\n"
                f"📌 *Stock:* `{p['symbol']}`\n"
                f"🎖️ *Conviction Score:* `{p['score']}/100 POINTS` 🔥\n"
                f"💰 *Current Price:* `₹{p['close']}`\n\n"
                f"🌐 *Macro Sector Context:*\n"
                f"• Top Sector: `{top_sector_name}` ({top_sector_gain}%)\n"
                f"• Cash Turnover: `₹{p['turnover_cr']} Crore`\n"
                f"• Volume Velocity: `{p['vol_x']}x Normal`\n\n"
                f"🔍 *Why Will It Blast? (Catalysts):*{reasons_bullet}\n\n"
                f"🎯 *Execution Targets & Runway:*\n"
                f"• 🎯 Target 1 (+5% Quick): `₹{p['t1']}`\n"
                f"• 🚀 Target 2 (+15% Swing): `₹{p['t2']}`\n"
                f"• 👑 Target 3 (+30% Multibagger): `₹{p['t3']}`\n"
                f"• 🛑 Strict SL: `₹{p['sl']}` (-{p['risk']}% Risk)\n\n"
                f"📋 *Trade Blueprint:*\n"
                f"1. Target 1 (+5%) par 50% profit book karein.\n"
                f"2. Baki quantity ka SL seedha Buy Price par trail karein (0% Risk)!\n"
                f"3. Daily 20-EMA ke sath Target 2 & 3 tak ride karein."
            )
            send_telegram(alert_text)
            print(f"Alert Sent for {p['symbol']}")
    else:
        print("Market Lab: No stock reached 80+ score today. Capital safe.")

if __name__ == "__main__":
    run_market_lab()
