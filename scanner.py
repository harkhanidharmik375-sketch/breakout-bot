import os, time, io, warnings, requests, pandas as pd, numpy as np, yfinance as yf
import xml.etree.ElementTree as ET
from datetime import datetime
warnings.filterwarnings('ignore')

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
sent_today = set()

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_news(sym):
    try:
        items = ET.fromstring(requests.get(f"https://news.google.com/rss/search?q={sym}+stock+NSE&hl=en-IN&gl=IN&ceid=IN:en", timeout=4).content).findall('.//item')[:2]
        return " | ".join([i.find('title').text.split(' - ')[0][:50] for i in items]) or "Order Block Retest Bounce"
    except: return "Institutional SMC Order Block Bounce"

def get_universe():
    try:
        r = requests.get("https://archives.nseindia.com/content/indices/ind_nifty500list.csv", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        return [f"{s}.NS" for s in pd.read_csv(io.StringIO(r.text))['Symbol'].dropna() if "DUMMY" not in s and "BAGMANE" not in s]
    except: return ["GREAVESCOT.NS", "HDFCBANK.NS", "INDUSINDBK.NS", "SGMART.NS", "SGFIN.NS", "MCX.NS", "CDSL.NS"]

def scan_smc_v4():
    stocks = get_universe()
    now_s = datetime.now().strftime("%I:%M %p")
    print(f"[{now_s}] Scanning {len(stocks)} stocks on SMC V4.1...")
    for k in range(0, len(stocks), 50):
        batch = stocks[k:k+50]
        try:
            data = yf.download(tickers=batch, period="25d", interval="15m", group_by="ticker", threads=True, progress=False, timeout=20)
            for sym in batch:
                if sym in sent_today: continue
                try:
                    df = (data[sym] if len(batch)>1 and sym in data.columns.get_level_values(0) else data.xs(sym, level=1, axis=1) if isinstance(data.columns, pd.MultiIndex) else data).dropna()
                    if len(df) < 205: continue
                    e20 = df['Close'].ewm(span=20).mean()
                    e50 = df['Close'].ewm(span=50).mean()
                    e200 = df['Close'].ewm(span=200).mean() # 1-Hour 50 EMA Anchor!
                    v_sma = df['Volume'].rolling(20).mean()
                    hl = df['High'] - df['Low']
                    hc = (df['High'] - df['Close'].shift(1)).abs()
                    lc = (df['Low'] - df['Close'].shift(1)).abs()
                    atr = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

                    c, o, h, l, v = float(df['Close'].iloc[-1]), float(df['Open'].iloc[-1]), float(df['High'].iloc[-1]), float(df['Low'].iloc[-1]), float(df['Volume'].iloc[-1])
                    c1, o1, h1, l1 = float(df['Close'].iloc[-2]), float(df['Open'].iloc[-2]), float(df['High'].iloc[-2]), float(df['Low'].iloc[-2])
                    
                    # Check Order Block & SMC V4.1 Rules
                    htf_bull = c > float(e200.iloc[-1])
                    trend_15 = (c > float(e50.iloc[-1])) and (float(e20.iloc[-1]) > float(e50.iloc[-1]))
                    ob_retest = (l1 <= float(e20.iloc[-2]) * 1.005) and (c1 < o1)
                    rev_bar = (c > o) and (c > c1)
                    vol_ok = v > (float(v_sma.iloc[-1]) * 1.25)
                    liq_ok = (40 < c < 15000) and (c * v >= 5000000)

                    if htf_bull and trend_15 and ob_retest and rev_bar and vol_ok and liq_ok:
                        cur_atr = float(atr.iloc[-1])
                        sl = round(max(c * 0.962, min(l1 * 0.99, c - max(1.8 * cur_atr, c * 0.022))), 2)
                        be = round(c * 1.022, 2)
                        clean_s = sym.replace(".NS", "")
                        msg = (
                            f"💎 *APEX SMC V4.1 LIVE BUY* 💎\n\n"
                            f"📌 *Stock:* `{clean_s}`\n"
                            f"💰 *Entry CMP:* `₹{round(c,2)}`\n"
                            f"🛑 *Initial Red SL:* `₹{sl}` (-{round((c-sl)/c*100,1)}%)\n"
                            f"🔵 *Blue Breakeven Trigger:* `₹{be}` (+2.2%)\n"
                            f"📊 *Vol:* `{round(v/float(v_sma.iloc[-1]),1)}x` | *15m Flow:* `₹{round(c*v/1e5,1)} L`\n"
                            f"📰 *News:* {get_news(clean_s)}\n\n"
                            f"⚡ *Action:* TradingView par `SMC BUY` confirm karein aur `TREND EXIT 💰` tak ride karein!"
                        )
                        send_telegram(msg)
                        sent_today.add(sym)
                except: continue
        except: continue
        time.sleep(0.5)

if __name__ == "__main__":
    send_telegram("💎 *SMC V4.1 Live Hunter Started!* Har 3 minute mein poora market scan hoga.")
    for _ in range(110):
        scan_smc_v4()
        time.sleep(180)
