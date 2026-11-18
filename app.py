import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components

# --- INDIA TIME FIX ---
IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="Upstox Gamma-Theta Live Scanner", layout="wide")
st.title("⚡ Upstox लाइव एक्सपायरी Gamma-Theta & OI डैशबोर्ड")

# --- SIDEBAR SETTINGS ---
st.sidebar.header("🔑 Upstox सेटिंग्स")
access_token = st.sidebar.text_input("Upstox Access Token डालें:", type="password")

index_choice = st.sidebar.selectbox(
    "इंडेक्स चुनें:", 
    [
        "NSE_INDEX|Nifty 50", 
        "NSE_INDEX|Nifty Bank", 
        "NSE_INDEX|Nifty Fin Service",
        "BSE_INDEX|SENSEX", 
    ]
)
expiry_date = st.sidebar.text_input("एक्सपायरी डेट (YYYY-MM-DD):", value="2026-11-19")
auto_refresh = st.sidebar.checkbox("हर 5 सेकंड में लाइव रिफ्रेश करें", value=False)

# --- LOCKS ---
st.sidebar.header("🔒 Lock Settings")
use_vwap_lock = st.sidebar.checkbox("VWAP Lock ON rakhe (Call upar / Put neeche)", value=True)
use_candle_lock = st.sidebar.checkbox("Candle Close Lock ON rakhe", value=True)
sound_on = st.sidebar.checkbox("🔔 Sound ON rakhe", value=True)

def fetch_upstox_option_chain(token, instrument_key, expiry):
    url = "https://upstox.com"
    params = {"instrument_key": instrument_key, "expiry_date": expiry}
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            try:
                return response.json().get("data", [])
            except Exception:
                return []
        else:
            st.error(f"API Error: {response.status_code} - {response.text[:200]} | Token check karein.")
            return []
    except Exception as e:
        st.error(f"Option Chain Connection Error: {e}")
        return []

def get_future_instrument_key(index_key):
    mapping = {
        "NSE_INDEX|Nifty 50": "NSE_FO|NIFTY",
        "NSE_INDEX|Nifty Bank": "NSE_FO|BANKNIFTY",
        "NSE_INDEX|Nifty Fin Service": "NSE_FO|FINNIFTY",
        "BSE_INDEX|SENSEX": "BSE_FO|SENSEX"
    }
    if index_key in mapping:
        return mapping[index_key]
    clean_key = index_key.replace("NSE_INDEX|", "NSE_FO|").replace("BSE_INDEX|", "BSE_FO|")
    if "Nifty " in clean_key:
        clean_key = clean_key.replace("Nifty ", "")
    return clean_key

def fetch_vwap(token, index_instrument_key):
    fut_key = get_future_instrument_key(index_instrument_key)
    url = "https://upstox.com"
    params = {"instrument_key": fut_key}
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            try:
                data_dict = r.json().get("data", {})
                for k, val in data_dict.items():
                    if fut_key in k:
                        return val.get("average_price", 0)
            except Exception:
                pass
    except Exception:
        pass
    return 0

def analyze_options(raw_data, selected_index, target_expiry, vwap_price):
    rows = []
    spot_price = 0
    today_str = datetime.now(IST).strftime('%Y-%m-%d')
    is_expiry_day = (today_str == target_expiry)
    filter_range = 1500 if "SENSEX" in selected_index else 500
    if is_expiry_day:
        min_volume = 100000
        min_oi_drop = 0
        market_status_label = "🔴 EXPIRY DAY MODE"
    else:
        min_volume = 30000
        min_oi_drop = 5000
        market_status_label = "🔵 NORMAL DAY MODE"
    now = datetime.now(IST)
    candle_closed = True
    if use_candle_lock and now.second > 10:
        candle_closed = False
            
    for item in raw_data:
        if spot_price == 0:
            spot_price = item.get("underlying_spot_price", 0)
        strike = item.get("strike_price", 0)
        if abs(spot_price - strike) > filter_range:
            continue
        for opt_type, key in [("CE", "call_options"), ("PE", "put_options")]:
            opt = item.get(key, {})
            mkt = opt.get("market_data", {})
            greeks = opt.get("option_greeks", {})
            ltp = mkt.get("ltp", 0)
            close_p = mkt.get("close_price", 0)
            vol = mkt.get("volume", 0)
            oi = mkt.get("oi", 0)
            prev_oi = mkt.get("prev_oi", 0)
            oi_change = oi - prev_oi
            delta = round(greeks.get("delta", 0), 2)
            gamma = round(greeks.get("gamma", 0), 4)
            theta = round(greeks.get("theta", 0), 2)
            cond_delta = 0.30 <= abs(delta) <= 0.55
            cond_gamma = gamma > 0.0005
            
            if is_expiry_day:
                cond_oi = oi_change < 0
                cond_momentum = (vol > min_volume) and (ltp > close_p)
            else:
                cond_oi = oi_change < -min_oi_drop or (oi_change < 0 and abs(oi_change) > (oi * 0.02))
                cond_momentum = (vol > min_volume) and (ltp > close_p)
            
            vwap_ok = True
            if use_vwap_lock and vwap_price > 0:
                if opt_type == "CE":
                    vwap_ok = spot_price > vwap_price
                else:
                    vwap_ok = spot_price < vwap_price
                    
            if cond_delta and cond_gamma and cond_oi and cond_momentum and candle_closed and vwap_ok:
                signal = f"🔥 GAMMA BLAST BUY ({opt_type})"
            elif cond_delta and cond_gamma and cond_momentum and vwap_ok:
                signal = f"🟡 WATCH - {opt_type} ki taiyari karo"
            elif oi_change > 50000 and ltp < close_p:
                signal = "⚠️ AVOID (Theta Decay)"
            else:
                signal = "⏳ WAIT"
            rows.append({"Type": opt_type, "Strike": strike, "LTP (₹)": ltp, "Delta": delta, "Gamma": gamma, "Theta": theta, "Volume": vol, "OI Change": oi_change, "SIGNAL": signal})
    return pd.DataFrame(rows), spot_price, market_status_label, candle_closed

def highlight_signal(val):
    if "GAMMA BLAST" in str(val):
        return 'background-color: #1b5e20; color: white; font-weight: bold;'
    elif "WATCH" in str(val):
        return 'background-color: #f9a825; color: black; font-weight: bold;'
    elif "AVOID" in str(val):
        return 'background-color: #b71c1c; color: white;'
    return ''

def play_sound():
    components.html("""
    <script>
    function beep(freq, start, dur){
        var ctx = new (window.AudioContext || window.webkitAudioContext)();
        var o = ctx.createOscillator(); var g = ctx.createGain();
        o.connect(g); g.connect(ctx.destination); o.frequency.value = freq; o.type = 'sine';
        var t = ctx.currentTime + start; g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(1, t+0.05); g.gain.exponentialRampToValueAtTime(0.001, t+dur);
        o.start(t); o.stop(t+dur+0.1);
    }
    beep(880, 0, 0.4); beep(880, 0.5, 0.4); beep(880, 1.0, 0.6);
    </script>
    <div style="color:green; font-weight:bold; font-size:18px;">🔔 SOUND BAJ RAHI HAI</div>
    """, height=50)

# --- APPLICATION FLOW CONTROL ---
if not access_token:
    st.warning("👈 शुरू करने के लिए बाईं तरफ अपना Upstox Access Token डालें।")
else:
    raw_data = fetch_upstox_option_chain(access_token, index_choice, expiry_date)
    vwap_val = fetch_vwap(access_token, index_choice)
    
    if not raw_data:
        st.error("🔴 DATA NAHI MIL RAHA - Token ya Expiry Date check karo.")
    else:
        df, spot, current_mode, candle_closed = analyze_options(raw_data, index_choice, expiry_date, vwap_val)
        st.info(f"⚙️ स्कैनर मोड: {current_mode}")
        ist_now_str = datetime.now(IST).strftime('%H:%M:%S')
        vwap_display = f"{vwap_val} (Fut)" if vwap_val > 0 else "FETCHING ERROR"
        st.subheader(f"📊 स्पॉट: {spot} | Future VWAP: {vwap_display} | समय (IST): {ist_now_str}")

        if not candle_closed:
            st.warning("⏳ Candle Close Lock: Candle band hone do...")
            
        if not df.empty:
            signal_df = df[df["SIGNAL"].str.contains("GAMMA BLAST")]
            watch_df = df[df["SIGNAL"].str.contains("WATCH")]
        else:
            signal_df = pd.DataFrame()
            watch_df = pd.DataFrame()
            
        if not signal_df.empty:
            for _, s in signal_df.iterrows():
                st.success(f"🚨 SIGNAL - {s['Strike']} {s['Type']} | LTP: {s['LTP (₹)']}")
            if sound_on:
                play_sound()
            st.dataframe(signal_df.style.map(highlight_signal, subset=['SIGNAL']), use_container_width=True)
        elif not watch_df.empty:
            st.warning("🟡 WATCH - Taiyaar raho, entry mat lo.")
            st.dataframe(watch_df.style.map(highlight_signal, subset=['SIGNAL']), use_container_width=True)
        else:
            st.info("⏳ WAIT Karo - Koi Signal Nahi Hai")
            
        with st.expander("Pura Option Chain"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 🟢 CALL (CE)")
                if not df.empty:
                    st.dataframe(df[df["Type"] == "CE"].drop(columns=["Type"]).style.map(highlight_signal, subset=['SIGNAL']), use_container_width=True)
            with col2:
                st.markdown("### 🔴 PUT (PE)")
                if not df.empty:
                    st.dataframe(df[df["Type"] == "PE"].drop(columns=["Type"]).style.map(highlight_signal, subset=['SIGNAL']), use_container_width=True)

# --- 🔄 GLOBAL AUTO REFRESH LOOP RUNNING AT THE ABSOLUTE END ---
if auto_refresh:
    time.sleep(5)
    st.rerun()
else:
    if st.sidebar.button("🔄 Manual Refresh Trigger"):
        st.rerun()
