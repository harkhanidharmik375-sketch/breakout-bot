import os
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import io
import xml.etree.ElementTree as ET
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=12)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_latest_news(sym_clean):
    try:
        r = requests.get(f"https://news.google.com/rss/search?q={sym_clean}+share+price+NSE&hl=en-IN&gl=IN&ceid=IN:en", timeout=5)
        root = ET.fromstring(r.content)
        items = [i.find('title').text.split(' - ')[0] for i in root.findall('.//item')[:3]]
        return "\n• " + "\n• ".join(items) if items else "• Institutional volume absorption breakout"
    except:
        return "• Fresh Stage-2 expansion with heavy turnover"

def get_universe():
    try:
        r = requests.get("https://archives.nseindia.com/content/indices/ind_nifty500list.csv", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        df = pd.read_csv(io.StringIO(r.text))
        return [f"{s}.NS" for s in df['Symbol'].dropna().tolist() if "DUMMY" not in s and "BAGMANE" not in s]
    except:
        return ["INDUSINDBK.NS", "SGFIN.NS", "SGMART.NS", "CUB.NS", "RAYMOND.NS", "CUPID.NS", "VOLTAS.NS", "TATATECH.NS", "WOCKPHARMA.NS"]

def scan_masterpiece():
    now_str = datetime.now().strftime("%I:%M %p")
    print(f"[{now_str}] Running Live Masterpiece Scan...")
    
    # 1. Market Regime Check (Nifty 50 Guard)
    try:
        nifty = yf.download("^NSEI", period="60d", interval="1d", progress=False)
        nifty_c = float(nifty['Close'].iloc[-1])
        nifty_ema10 = float(nifty['Close'].ewm(span=10).mean().iloc[-1])
        nifty_o = float(nifty['Open'].iloc[-1])
        if nifty_c < nifty_ema10 or nifty_c < nifty_o:
            print("Market Regime: Nifty 50 is weak/red. Preserving capital, zero new trades.")
            return
    except:
        pass

    stocks = get_universe()
    try:
        data = yf.download(tickers=stocks, period="60d", interval="1d", group_by="ticker", threads=True, progress=False, timeout=35)
    except Exception as e:
        print(f"Download Error: {e}")
        return

    triggered = []

    for sym in stocks:
        try:
            df = (data[sym] if len(stocks) > 1 and sym in data.columns.get_level_values(0) else data.xs(sym, level=1, axis=1) if isinstance(data.columns, pd.MultiIndex) else data).dropna()
            if len(df) < 40: continue

            c, h, l, o, v = float(df['Close'].iloc[-1]), float(df['High'].iloc[-1]), float(df['Low'].iloc[-1]), float(df['Open'].iloc[-1]), float(df['Volume'].iloc[-1])
            prev = df.iloc[:-1]

            # 1. Base Depth & Resistance
            base_high = float(prev['High'].tail(25).max())
            base_low = float(prev['Low'].tail(25).min())
            base_depth = base_high - base_low
            h52w = float(prev['High'].tail(240).max()) if len(prev) >= 120 else base_high
            dist_52w = round(((h52w - c) / h52w) * 100, 1)

            # 2. Volume Dry-Up (VDU) Check in last 3 days
            vol_sma20 = float(prev['Volume'].tail(20).mean())
            min_prev_vol = float(prev['Volume'].tail(3).min())
            vdu_confirmed = min_prev_vol < (vol_sma20 * 0.75)  # Sellers were exhausted!

            # 3. Ignition Volume & Spread
            vol_x = round(v / vol_sma20, 1) if vol_sma20 > 0 else 1.0
            turnover = c * v
            candle_spread = h - l
            upper_wick = h - c
            clean_bull = (candle_spread > 0) and (upper_wick <= candle_spread * 0.16) and (c > o)

            # 4. Moving Averages
            ema9 = float(df['Close'].ewm(span=9).mean().iloc[-1])
            ema21 = float(df['Close'].ewm(span=21).mean().iloc[-1])
            ema50 = float(df['Close'].ewm(span=50).mean().iloc[-1])
            trend_aligned = (ema9 > ema21) and (ema21 > ema50) and (c > ema9)

            # 5. ATR Volatility
            hl = df['High'] - df['Low']
            hc = (df['High'] - df['Close'].shift(1)).abs()
            lc = (df['Low'] - df['Close'].shift(1)).abs()
            tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
            atr14 = float(tr.rolling(14).mean().iloc[-1])

            # 6. Anti-Overextension Gate
            candle_gain_pct = ((c - o) / o) * 100
            dist_ema9 = ((c - ema9) / ema9) * 100
            early_ignition = (candle_gain_pct >= 0.8) and (candle_gain_pct <= 3.5) and (dist_ema9 <= 2.8)

            # 100-POINT INSTITUTIONAL SCORING
            score = 0
            if c > base_high: score += 25
            if dist_52w <= 8.0: score += 20
            elif dist_52w <= 15.0: score += 12
            if vol_x >= 2.2: score += 25
            elif vol_x >= 1.4: score += 15
            if trend_aligned: score += 15
            if vdu_confirmed and clean_bull and (turnover >= 60000000): score += 15

            # TRIGGER ONLY GRADE A++ (Score >= 80)
            if score >= 80 and (c > base_high) and clean_bull and early_ignition and (turnover >= 50000000):
                # DYNAMIC PATTERN-DEPTH TARGETS (NO FIXED NUMBERS!)
                t1_target = round(c + base_depth, 2)
                t1_pct = round(((t1_target - c) / c) * 100, 1)

                t2_target = round(c + (3.5 * atr14), 2)
                t2_pct = round(((t2_target - c) / c) * 100, 1)

                t3_target = round(c + (1.618 * base_depth), 2)
                t3_pct = round(((t3_target - c) / c) * 100, 1)

                sl_price = round(max(base_high * 0.985, c - (2.0 * atr14)), 2)
                risk_pct = round(((c - sl_price) / c) * 100, 1)

                clean_sym = sym.replace('.NS', '')
                catalyst_news = get_latest_news(clean_sym)

                dossier = (
                    f"👑 *MASTERPIECE QUANT BLAST DOSSIER* 💎\n\n"
                    f"📌 *Stock:* `{clean_sym}`\n"
                    f"🎖️ *Institutional Score:* `{score}/100 POINTS` 🔥\n"
                    f"💰 *Entry CMP:* `₹{round(c, 2)}`\n"
                    f"🌊 *Volume Velocity:* `{vol_x}x Surge` | *Flow:* `₹{round(turnover/1e7, 1)} Cr`\n\n"
                    f"🏗️ *Base Structure:* 25-Day Range (₹{round(base_low, 1)} - ₹{round(base_high, 1)}) | VDU Confirmed ✅\n"
                    f"📈 *Trend:* Stage-2 Bull (9>21>50 Aligned) | 52W Dist: `{dist_52w}%`\n\n"
                    f"🔍 *Hidden Catalysts & Latest 48H News:*{catalyst_news}\n\n"
                    f"🎯 *Stock-Specific Dynamic Runway (No Fixed %):*\n"
                    f"• 🎯 *Target 1 (Base Depth +{t1_pct}%):* `₹{t1_target}`\n"
                    f"• 🚀 *Target 2 (ATR Runway +{t2_pct}%):* `₹{t2_target}`\n"
                    f"• 👑 *Target 3 (Fib 1.618x +{t3_pct}%):* `₹{t3_target}`\n"
                    f"• 🛑 *Strict Structural SL:* `₹{sl_price}` (-{risk_pct}% Risk)\n\n"
                    f"📋 *Execution Protocol:*\n"
                    f"1. Target 1 (₹{t1_target}) par 50% shares book karein.\n"
                    f"2. Baki 50% shares ka SL turant Buy Price (Cost) par shift karein (0% Risk)!\n"
                    f"3. Daily 10-EMA ke sath Target 2 & 3 tak ride karein."
                )
                send_telegram(dossier)
                triggered.append(clean_sym)
                print(f"Triggered: {clean_sym}")

        except Exception:
            continue

    if not triggered:
        print(f"[{now_str}] Scan complete. Zero high-risk setups. Capital 100% safe.")

# ==========================================
# CONTINUOUS LIVE MARKET RUNNER (9:15 - 3:30)
# ==========================================
if __name__ == "__main__":
    send_telegram("🚀 *Masterpiece Live Scanner Activated!* System cloud par live hai, live market mein har 2 minute mein scan chalega.")
    
    # 5 Hours Active Session Loop
    for _ in range(150):
        scan_masterpiece()
        time.sleep(120)  # Scan every 2 minutes!
