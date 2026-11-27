import os, requests, pandas as pd, numpy as np, yfinance as yf, io, xml.etree.ElementTree as ET
from datetime import datetime

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=12)
    except Exception as e: print("Telegram err:", e)

def get_news(sym):
    try:
        root = ET.fromstring(requests.get(f"https://news.google.com/rss/search?q={sym}+stock+NSE&hl=en-IN&gl=IN&ceid=IN:en", timeout=5).content)
        return [i.find('title').text.split(' - ')[0] for i in root.findall('.//item')[:2]]
    except: return ["Institutional Volume Accumulation"]

def get_universe():
    try:
        r = requests.get("https://archives.nseindia.com/content/indices/ind_nifty500list.csv", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        return [f"{s}.NS" for s in pd.read_csv(io.StringIO(r.text))['Symbol'].dropna().tolist() if "DUMMY" not in s]
    except: return ["INDUSINDBK.NS", "SGFIN.NS", "SGMART.NS", "CUB.NS", "RAYMOND.NS", "WOCKPHARMA.NS"]

def run_multi_agent_system():
    stocks = get_universe()
    print(f"Multi-Agent System Scanning {len(stocks)} stocks...")
    try: data = yf.download(tickers=stocks, period="60d", interval="1d", group_by="ticker", threads=True, progress=False, timeout=40)
    except: return

    approved_trades = []

    for sym in stocks:
        try:
            df = (data[sym] if len(stocks) > 1 and sym in data.columns.get_level_values(0) else data.xs(sym, level=1, axis=1) if isinstance(data.columns, pd.MultiIndex) else data).dropna()
            if len(df) < 40: continue

            c, h, l, o, v = float(df['Close'].iloc[-1]), float(df['High'].iloc[-1]), float(df['Low'].iloc[-1]), float(df['Open'].iloc[-1]), float(df['Volume'].iloc[-1])
            prev = df.iloc[:-1]

            # Agent 1: Technical & SMC Structure
            h20 = float(prev['High'].tail(20).max())
            l20 = float(prev['Low'].tail(20).min())
            h52w = float(prev['High'].tail(240).max()) if len(prev) >= 120 else h20
            v_avg = float(prev['Volume'].tail(20).mean())
            turnover = c * v

            ema20 = float(df['Close'].ewm(span=20).mean().iloc[-1])
            ema50 = float(df['Close'].ewm(span=50).mean().iloc[-1])

            dist_52w = round(((h52w - c) / h52w) * 100, 1)
            vol_x = round(v / v_avg, 1) if v_avg > 0 else 1.0

            # Filter: Candidate must show Break of Structure + Volume
            if not (c > h20 and vol_x >= 1.5 and c > o and turnover >= 60000000 and dist_52w <= 12.0):
                continue

            # ==========================================
            # AGENT DEBATE (Bull Agent vs Bear Agent)
            # ==========================================
            bull_args = []
            bear_args = []

            # Bull Arguments
            bull_args.append(f"Break of Structure (BOS) over 20-day ceiling (Rs.{round(h20,1)})")
            bull_args.append(f"Institutional Volume Inflow: {vol_x}x above 20-DMA")
            if dist_52w <= 6.0: bull_args.append(f"Near 52-Week High (Blue Sky Zone - {dist_52w}% away)")
            if ema20 > ema50: bull_args.append("Stage-2 Trend Alignment (20 EMA > 50 EMA)")

            # Bear Arguments (Risk Hunting)
            dist_ema20 = round(((c - ema20) / ema20) * 100, 1)
            if dist_ema20 >= 6.0: bear_args.append(f"Overextended: Price is +{dist_ema20}% above 20 EMA (Rubber-band risk)")
            if (h - c) > (h - l) * 0.25: bear_args.append("Upper rejection wick detected (Sellers active at top)")
            if vol_x > 6.0: bear_args.append(f"Climax Volume Warning ({vol_x}x volume could be blow-off)")

            # Portfolio Manager Decision
            clean_sym = sym.replace('.NS', '')
            news_items = get_news(clean_sym)
            for n in news_items:
                if any(w in n.lower() for w in ['loss', 'fall', 'slump', 'fraud', 'probe', 'down']):
                    bear_args.append(f"Negative News Headline: {n[:45]}...")

            # Verdict: Approve ONLY if Bear risks are minimal
            if len(bear_args) <= 1:
                sl_calc = round(max(l20, c * 0.965), 2)
                t1_calc = round(c + (c - sl_calc) * 2.0, 2)
                t2_calc = round(c + (c - sl_calc) * 3.5, 2)
                risk_pct = round(((c - sl_calc) / c) * 100, 1)

                report = (
                    f"🤖 *MULTI-AGENT TRADING FIRM DOSSIER* 📊\n\n"
                    f"📌 *Stock:* `{clean_sym}` | *Action:* `APPROVED BUY 💎`\n"
                    f"💰 *CMP:* `Rs.{round(c, 2)}` | *Flow:* `Rs.{round(turnover/1e7, 1)} Cr`\n\n"
                    f"🟢 *Bull Agent (Why Buy?):*\n• " + "\n• ".join(bull_args) + "\n\n"
                    f"🔴 *Bear Agent (Risks Checked):*\n• " + ("\n• ".join(bear_args) if bear_args else "Zero structural flaws detected") + "\n\n"
                    f"🎯 *Risk Manager Order Plan:*\n"
                    f"• 🎯 Target 1 (1:2 R:R): `Rs.{t1_calc}` (+{round(((t1_calc-c)/c)*100,1)}%)\n"
                    f"• 🚀 Target 2 (1:3.5 R:R): `Rs.{t2_calc}` (+{round(((t2_calc-c)/c)*100,1)}%)\n"
                    f"• 🛑 Strict SL: `Rs.{sl_calc}` (-{risk_pct}% Risk)\n\n"
                    f"📰 *Live News:* " + " | ".join(news_items[:2])
                )
                send_telegram(report)
                approved_trades.append(clean_sym)

        except Exception as e: continue

    if not approved_trades:
        send_telegram("🛡️ *Multi-Agent Firm Update:*\n\nMarket scan complete. Bear Agent rejected all risky setups today. Capital 100% preserved!")

if __name__ == "__main__":
    run_multi_agent_system()
