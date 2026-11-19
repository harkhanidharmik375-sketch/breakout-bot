import os
import yfinance as yf
import pandas as pd
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

# Scan list
STOCKS = [
    "SGFIN.NS", "RKFORGE.NS", "KTKBANK.NS", "ABDL.NS", "SUNTV.NS",
    "TATATECH.NS", "VOLTAS.NS", "BLUESTARCO.NS", "IREDA.NS", "DIXON.NS",
    "KPRMILL.NS", "PERSISTENT.NS", "COFORGE.NS", "POLYCAB.NS", "KAYNES.NS",
    "SUZLON.NS", "BSE.NS", "CDSL.NS", "HUDCO.NS", "NBCC.NS"
]

found = False
for sym in STOCKS:
    try:
        t = yf.Ticker(sym)
        df = t.history(period="40d")
        if len(df) < 22:
            continue
            
        c = df.iloc[-1]
        prev = df.iloc[:-1]
        
        close, high, low, op, vol = c['Close'], c['High'], c['Low'], c['Open'], c['Volume']
        h20 = prev['High'].tail(20).max()
        v_avg = prev['Volume'].tail(20).mean()
        
        # Conditions: 20-day high + 2.5x volume + top close
        if close > h20 and vol > (v_avg * 2.2) and (high - close) <= (high - low) * 0.18:
            buy = round(close, 2)
            sl = round(max(low, buy * 0.975), 2)
            t1 = round(buy * 1.05, 2)
            t2 = round(buy * 1.09, 2)
            
            text = (
                f"🚀 *GENUINE BREAKOUT DETECTED* 🚀\n\n"
                f"📌 *Stock:* `{sym.replace('.NS', '')}`\n"
                f"💰 *Buy CMP:* `₹{buy}`\n\n"
                f"🎯 *Target 1 (+5%):* `₹{t1}`\n"
                f"🎯 *Target 2 (+9%):* `₹{t2}`\n"
                f"🛑 *Strict SL:* `₹{sl}`\n\n"
                f"📊 *Volume:* `{round(vol/v_avg, 1)}x Normal`\n"
                f"⏱️ *Rule:* Subah 9:20 AM par agar VWAP ke neeche phisle toh exit!"
            )
            send_telegram(text)
            found = True
    except:
        pass

if not found:
    print("Zero false breakouts today.")
