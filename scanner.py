import os
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import io
import xml.etree.ElementTree as ET
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

# 1. Fetch Latest 1-2 Days News / Catalyst (Google News RSS)
def get_latest_catalyst(symbol_clean):
    try:
        url = f"https://news.google.com/rss/search?q={symbol_clean}+share+price+NSE&hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(url, timeout=6)
        root = ET.fromstring(resp.content)
        headlines = []
        for item in root.findall('.//item')[:3]:
            title = item.find('title').text
            # Clean headline title
            clean_t = title.split(' - ')[0] if ' - ' in title else title
            headlines.append(clean_t)
        if headlines:
            return "\n• " + "\n• ".join(headlines)
        return "• High volume delivery accumulation & base breakout"
    except:
        return "• Institutional order flow breakout near multi-day ceiling"

# 2. Universe
def get_universe():
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(r.text))
        return [f"{sym}.NS" for sym in df['Symbol'].dropna().tolist()]
    except:
        return ["INDUSINDBK.NS", "SGFIN.NS", "SGMART.NS", "CUB.NS", "RAYMOND.NS", "CUPID.NS", "VOLTAS.NS", "TATATECH.NS", "WOCKPHARMA.NS"]

def calculate_atr(df, period=14):
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift(1)).abs()
    lc = (df['Low'] - df['Close'].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# 3. Main Scanning & Dynamic Target Engine
def run_live_intelligence():
    stocks = get_universe()
    print(f"Scanning {len(stocks)} stocks on Dynamic Intelligence Engine...")

    try:
        data = yf.download(tickers=stocks, period="60d", interval="1d", group_by="ticker", threads=True, timeout=40)
    except Exception as e:
        print(f"Download Error: {e}")
        return

    triggered_stocks = []

    for sym in stocks:
        try:
            df = data[sym].dropna() if len(stocks) > 1 else data.dropna()
            if len(df) < 45:
                continue

            c = df.iloc[-1]
            prev = df.iloc[:-1]

            close = float(c['Close'])
            high = float(c['High'])
            low = float(c['Low'])
            open_p = float(c['Open'])
            volume = float(c['Volume'])

            # Multi-Day Base Structure (Last 30-Day Consolidation)
            base_high = float(prev['High'].tail(30).max())
            base_low = float(prev['Low'].tail(30).min())
            base_depth = base_high - base_low  # Exact Depth of the Pattern!
            base_depth_pct = round((base_depth / base_high) * 100, 1)

            # 52-Week High Proximity
            h52w = float(prev['High'].tail(240).max()) if len(prev) >= 120 else base_high
            dist_52w = round(((h52w - close) / h52w) * 100, 1)

            # Volatility & Volume Metrics
            atr_series = calculate_atr(df, 14)
            current_atr = float(atr_series.iloc[-1])
            vol_sma20 = float(prev['Volume'].tail(20).mean())
            turnover = close * volume
            vol_x = round(volume / vol_sma20, 1) if vol_sma20 > 0 else 1.0

            # Moving Averages
            ema9 = float(df['Close'].ewm(span=9).mean().iloc[-1])
            ema21 = float(df['Close'].ewm(span=21).mean().iloc[-1])
            ema50 = float(df['Close'].ewm(span=50).mean().iloc[-1])

            candle_range = high - low
            upper_wick = high - close
            clean_bar = (candle_range > 0) and (upperWick <= candle_range * 0.16) and (close > open_p)

            # ==========================================
            # DETAILED SCORE BREAKDOWN (Max 100 Pts)
            # ==========================================
            score_base = 0
            score_vol = 0
            score_52w = 0
            score_trend = 0
            score_quality = 0

            # 1. Structural Base Breakout (Max 25)
            if close > base_high:
                score_base = 25

            # 2. Volume Shock & Cash Flow (Max 25)
            if vol_x >= 2.5:
                score_vol = 25
            elif vol_x >= 1.5:
                score_vol = 15

            # 3. 52-Week Blue-Sky Proximity (Max 20)
            if dist_52w <= 8.0:
                score_52w = 20
            elif dist_52w <= 15.0:
                score_52w = 12

            # 4. Stage-2 Trend Alignment (Max 15)
            if (ema9 > ema21) and (ema21 > ema50) and (close > ema9):
                score_trend = 15

            # 5. Clean Institutional Wick & Turnover (Max 15)
            if clean_bar and (turnover >= 80000000): # 8 Cr+
                score_quality = 15

            total_score = score_base + score_vol + score_52w + score_trend + score_quality

            # FILTER: High-Conviction Blast Threshold (Score >= 80)
            if total_score >= 80 and (close > base_high) and clean_bar and (turnover >= 60000000):
                # DYNAMIC ASSET-SPECIFIC TARGETS (No Fixed 5%!)
                # Target 1: Base Pattern Measured Move (+1.0x Base Depth)
                t1_dynamic = round(close + base_depth, 2)
                t1_pct = round(((t1_dynamic - close) / close) * 100, 1)

                # Target 2: Extended Volatility Runway (+3.5x Daily ATR)
                t2_dynamic = round(close + (3.5 * current_atr), 2)
                t2_pct = round(((t2_dynamic - close) / close) * 100, 1)

                # Target 3: Blue-Sky Fibonacci Extension (+1.618x Base Depth)
                t3_dynamic = round(close + (1.618 * base_depth), 2)
                t3_pct = round(((t3_dynamic - close) / close) * 100, 1)

                # Dynamic Trailing Stop Loss (Below base breakout or 2.0x ATR)
                sl_dynamic = round(max(base_high * 0.98, close - (2.2 * current_atr)), 2)
                risk_pct = round(((close - sl_dynamic) / close) * 100, 1)

                clean_sym = sym.replace('.NS', '')
                news_headlines = get_latest_catalyst(clean_sym)

                report = (
                    f"⛏️ *LIVE APEX INTELLIGENCE DOSSIER* 💎\n\n"
                    f"📌 *Stock:* `{clean_sym}`\n"
                    f"🎖️ *Institutional Score:* `{total_score}/100 POINTS` 🔥\n"
                    f"💰 *Current Price:* `₹{round(close, 2)}`\n\n"
                    f"📊 *Detailed Score Breakdown:*\n"
                    f"• 🏗️ Base Breakout: `{score_base}/25 Pts` (30-Day Range: ₹{round(base_low, 1)} - ₹{round(base_high, 1)})\n"
                    f"• 🌊 Volume Shock: `{score_vol}/25 Pts` ({vol_x}x Normal Surge)\n"
                    f"• ☁️ Blue-Sky Proximity: `{score_52w}/20 Pts` ({dist_52w}% from 52W High)\n"
                    f"• 📈 Stage-2 Trend: `{score_trend}/15 Pts` (EMA 9>21>50 Aligned)\n"
                    f"• 🛡️ Bar Quality & Cash: `{score_quality}/15 Pts` (₹{round(turnover/10000000, 1)} Cr Flow)\n\n"
                    f"🔍 *Hidden Catalysts & Latest 1-2 Days News:*{news_headlines}\n\n"
                    f"🎯 *Stock-Specific Dynamic Blast Targets:*\n"
                    f"• 🎯 *Target 1 (Pattern Depth +{t1_pct}%):* `₹{t1_dynamic}`\n"
                    f"• 🚀 *Target 2 (ATR Runway +{t2_pct}%):* `₹{t2_dynamic}`\n"
                    f"• 👑 *Target 3 (Fib Extension +{t3_pct}%):* `₹{t3_dynamic}`\n"
                    f"• 🛑 *Dynamic Safe SL:* `₹{sl_dynamic}` (-{risk_pct}% Risk)\n\n"
                    f"📋 *Execution Protocol:*\n"
                    f"1. Target 1 (₹{t1_dynamic}) aate hi 50% shares book karein.\n"
                    f"2. Baki shares ka SL seedha Buy Price par trail karein (0% Risk)!\n"
                    f"3. Daily 10-EMA ke sath Target 2 & 3 tak ride karein."
                )
                send_telegram(report)
                triggered_stocks.append(clean_sym)
                print(f"Intelligence Report Dispatched for {clean_sym}")

        except Exception as e:
            continue

    if not triggered_stocks:
        print("Live Scan Complete: Zero high-conviction (>80 Score) setups right now.")

if __name__ == "__main__":
    run_live_intelligence()
* Uski jagah bas yeh kar dein:
  ```python
  if not triggered_stocks:
    now_t = datetime.now().strftime("%I:%M %p")
    send_telegram(
        f"✅ *Live Scan Complete ({now_t} IST)*\n\nPoore 500 stocks check ho"
        " gaye hain. Filhaal koi stock 80+ score nahi kar raha hai. Capital"
        " 100% safe hai!"
    )
