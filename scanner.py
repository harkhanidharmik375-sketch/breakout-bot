import os
import requests
import pandas as pd
import yfinance as yf
import io

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

def get_market_stocks():
    """NSE se Poore NIFTY 500 stocks ki live list fetch karta hai"""
    url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(r.text))
        symbols = [f"{sym}.NS" for sym in df['Symbol'].dropna().tolist()]
        print(f"Total {len(symbols)} stocks fetched from NSE!")
        return symbols
    except Exception as e:
        print(f"NSE Fetch Failed: {e}. Using High-Momentum Fallback List.")
        # Top 100 Momentum Fallback list agar NSE site busy ho
        return [
            "SGFIN.NS", "RKFORGE.NS", "KTKBANK.NS", "ABDL.NS", "SUNTV.NS",
            "TATATECH.NS", "VOLTAS.NS", "BLUESTARCO.NS", "IREDA.NS", "DIXON.NS",
            "KPRMILL.NS", "PERSISTENT.NS", "COFORGE.NS", "POLYCAB.NS", "KAYNES.NS",
            "SUZLON.NS", "BSE.NS", "CDSL.NS", "HUDCO.NS", "NBCC.NS", "BEL.NS",
            "HAL.NS", "TRENT.NS", "ZOMATO.NS", "JIOFIN.NS", "PRESTIGE.NS",
            "OBEROIRLTY.NS", "COCHINSHIP.NS", "MAZDOCK.NS", "RVNL.NS", "IRFC.NS",
            "FEDERALBNK.NS", "MOTHERSON.NS", "COLPAL.NS", "MCX.NS", "ANGELONE.NS"
        ]

def scan_full_market():
    stocks = get_market_stocks()
    print(f"Scanning {len(stocks)} stocks using Fast Multi-Threading...")
    
    # Batch download poore market ka ek sath (Super Fast 20 seconds)
    try:
        data = yf.download(tickers=stocks, period="35d", group_by="ticker", threads=True, timeout=30)
    except Exception as e:
        print(f"Download Error: {e}")
        return

    found_count = 0
    
    for sym in stocks:
        try:
            if len(stocks) > 1:
                df = data[sym].dropna()
            else:
                df = data.dropna()
                
            if len(df) < 22:
                continue
                
            c = df.iloc[-1]
            prev = df.iloc[:-1]
            
            close = float(c['Close'])
            high = float(c['High'])
            low = float(c['Low'])
            open_p = float(c['Open'])
            volume = float(c['Volume'])
            
            h20 = float(prev['High'].tail(20).max())
            v_avg = float(prev['Volume'].tail(20).mean())
            turnover = close * volume
            
            candle_range = high - low
            upper_wick = high - close
            
            # QUANT RULES:
            # 1. 20-Day Range Breakout
            is_breakout = close > h20
            # 2. Volume Blast (2.2x of 20-day average)
            is_vol_surge = volume > (v_avg * 2.2)
            # 3. Clean Candle (Upper wick <= 18% of day range, no late dumping)
            is_clean_close = (upper_wick <= candle_range * 0.18) if candle_range > 0 else False
            # 4. Healthy Move (Between +2.5% and +7.5%)
            is_sweet_move = (close >= open_p * 1.025) and (close <= open_p * 1.075)
            # 5. Turnover Filter (Min 10 Crore Cash Volume)
            is_liquid = turnover >= 100000000
            
            if is_breakout and is_vol_surge and is_clean_close and is_sweet_move and is_liquid:
                buy = round(close, 2)
                sl = round(max(low, buy * 0.975), 2)
                t1 = round(buy * 1.05, 2)   # +5%
                t2 = round(buy * 1.09, 2)   # +9%
                vol_x = round(volume / v_avg, 1)
                
                msg = (
                    f"🚀 *FULL MARKET BREAKOUT ALERT* 🚀\n\n"
                    f"📌 *Stock:* `{sym.replace('.NS', '')}`\n"
                    f"💰 *Buy CMP:* `₹{buy}`\n\n"
                    f"🎯 *Target 1 (+5%):* `₹{t1}`\n"
                    f"🎯 *Target 2 (+9%):* `₹{t2}`\n"
                    f"🛑 *Strict SL:* `₹{sl}`\n\n"
                    f"📊 *Volume:* `{vol_x}x Normal Surge`\n"
                    f"💵 *Turnover:* `₹{round(turnover/10000000, 1)} Cr`\n"
                    f"⏱️ *Rule:* Subah 9:20 AM par VWAP ke neeche phisle toh exit!"
                )
                send_telegram(msg)
                found_count += 1
                print(f"Triggered: {sym}")
                
        except Exception:
            continue
            
    print(f"Scan Complete! Total Breakouts Found: {found_count}")

if __name__ == "__main__":
    scan_full_market()
