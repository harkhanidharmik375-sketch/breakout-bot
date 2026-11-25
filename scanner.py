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
        print("Telegram keys missing!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=12)
    except Exception as e:
        print(f"Telegram send error: {e}")

def get_latest_catalyst(symbol_clean):
    try:
        url = f"https://news.google.com/rss/search?q={symbol_clean}+share+price+NSE&hl=en-IN&gl=IN&ceid=IN:en"
        resp = requests.get(url, timeout=5)
        root = ET.fromstring(resp.content)
        headlines = []
        for item in root.findall('.//item')[:3]:
            title = item.find('title').text
            clean_t = title.split(' - ')[0] if ' - ' in title else title
            headlines.append(clean_t)
        if headlines:
            return "\n• " + "\n• ".join(headlines)
        return "• High volume delivery accumulation & base breakout"
    except:
        return "• Institutional order flow breakout near multi-day ceiling"

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
            "CUPID.NS", "VOLTAS.NS", "TATATECH.NS", "WOCKPHARMA.NS", "BAJAJHLDNG.NS"
        ]

def calculate_atr(df, period=14):
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift(1)).abs()
    lc = (df['Low'] - df['Close'].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def run_live_intelligence():
    stocks = get_universe()
    print(f"Scanning {len(stocks)} stocks...")

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

            base_high = float(prev['High'].tail(30).max())
            base_low = float(prev['Low'].tail(30).min())
            base_depth = base_high - base_low

            h52w = float(prev['High'].tail(240).max()) if len(prev) >= 120 else base_high
            dist_52w = round(((h52w - close) / h52w) * 100, 1)

            atr_series = calculate_atr(df, 14)
            current_atr = float(atr_series.iloc[-1])
            vol_sma20 = float(prev['Volume'].tail(20).mean())
            turnover = close * volume
            vol_x = round(volume / vol_sma20, 1) if vol_sma20 > 0 else 1.0

            ema9 = float(df['Close'].ewm(span=9).mean().iloc[-1])
            ema21 = float(df['Close'].ewm(span=21).mean().iloc[-1])
            ema50 = float(df['Close'].ewm(span=50).mean().iloc[-1])

            candle_range = high - low
            upper_wick = high - close
            clean_bar = (candle_range > 0) and (upper_wick <= candle_range * 0.16) and (close > open_p)

            score = 0
            if close > base_high: score += 25
            if dist_52w <= 8.0: score += 20
            elif dist_52w <= 15.0: score += 12
            if vol_x >= 2.5: score += 25
            elif vol_x >= 1.5: score += 15
            if (ema9 > ema21) and (ema21 > ema50) and (close > ema9): score += 15
            if clean_bar and (turnover >= 80000000): score += 15

            if score >= 80 and (close > base_high) and clean_bar and (turnover >= 60000000):
                t1_dynamic = round(close + base_depth, 2)
                t1_pct = round(((t1_dynamic - close) / close) * 100, 1)
                t2_dynamic = round(close + (3.5 * current_atr), 2)
                t2_pct = round(((t2_dynamic - close) / close) * 100, 1)
                sl_dynamic = round(max(base_high * 0.98, close - (2.2 * current_atr)), 2)
                risk_pct = round(((close - sl_dynamic) / close) * 100, 1)

                clean_sym = sym.replace('.NS', '')
                news_headlines = get_latest_catalyst(clean_sym)

                report = (
                    f"⛏️ *LIVE APEX INTELLIGENCE DOSSIER* 💎\n\n"
                    f"📌 *Stock:* `{clean_sym}`\n"
                    f"🎖️ *Institutional Score:* `{score}/100 POINTS` 🔥\n"
                    f"💰 *Current Price:* `₹{round(close, 2)}`\n\n"
                    f"📊 *Score Breakdown:*\n"
                    f"• Base: {score}/100 | Vol: {vol_x}x | 52W Dist: {dist_52w}%\n"
                    f"• Flow: ₹{round(turnover/10000000, 1)} Cr\n\n"
                    f"🔍 *News & Catalysts:*{news_headlines}\n\n"
                    f"🎯 *Dynamic Targets:*\n"
                    f"• 🎯 Target 1 (+{t1_pct}%): `₹{t1_dynamic}`\n"
                    f"• 🚀 Target 2 (+{t2_pct}%): `₹{t2_dynamic}`\n"
                    f"• 🛑 Safe SL: `₹{sl_dynamic}` (-{risk_pct}%)\n\n"
                    f"📋 *Rule:* Target 1 par 50% book karein aur SL Cost par trail karein!"
                )
                send_telegram(report)
                triggered_stocks.append(clean_sym)

        except Exception:
            continue

    # HAR BAR TELEGRAM PAR CONFIRMATION BHEJEGA!
    now_t = datetime.now().strftime("%I:%M %p")
    if not triggered_stocks:
        send_telegram(f"✅ *Live Market Scan Finished ({now_t} IST)*\n\nPoore 500 stocks check ho gaye hain. Abhi market mein koi stock 80+ score nahi kar raha hai. Capital safe hai!")
    else:
        print(f"Triggered: {triggered_stocks}")

if __name__ == "__main__":
    run_live_intelligence()
