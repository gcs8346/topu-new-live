import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
import streamlit.components.v1 as components

# पेज सेटअप
st.set_page_config(page_title="Upstox Gamma-Theta Live Scanner", layout="wide")
st.title("⚡ Upstox लाइव एक्सपायरी Gamma-Theta & OI डैशबोर्ड")

# साइडबार में Upstox API और एक्सपायरी की जानकारी
st.sidebar.header("🔑 Upstox सेटिंग्स")
access_token = st.sidebar.text_input("Upstox Access Token डालें:", type="password")

index_choice = st.sidebar.selectbox(
    "इंडेक्स चुनें:", 
    [
        "NSE_INDEX|Nifty 50", 
        "NSE_INDEX|Nifty Bank", 
        "NSE_INDEX|Nifty Fin Service",
        "BSE_INDEX|SENSEX"
    ]
)
expiry_date = st.sidebar.text_input("एक्सपायरी डेट (YYYY-MM-DD):", value="2026-11-19")
auto_refresh = st.sidebar.checkbox("हर 5 सेकंड में लाइव रिफ्रेश करें", value=False)

# --- NAYE LOCK ---
st.sidebar.header("🔒 Lock Settings")
use_vwap_lock = st.sidebar.checkbox("VWAP Lock ON rakhe (Call upar / Put neeche)", value=True)
use_candle_lock = st.sidebar.checkbox("Candle Close Lock ON rakhe", value=True)
sound_on = st.sidebar.checkbox("🔔 Sound ON rakhe", value=True)

def fetch_upstox_option_chain(token, instrument_key, expiry):
    url = "https://api.upstox.com/v2/option/chain"
    params = {"instrument_key": instrument_key, "expiry_date": expiry}
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            st.error(f"API Error: {response.status_code} - {response.text[:200]} | Token aur Expiry Date जांचें।")
            return []
    except Exception as e:
        st.error(f"कनेक्शन एरर: {e}")
        return []

def fetch_vwap(token, instrument_key):
    url = "https://api.upstox.com/v2/market-quote/quotes"
    params = {"instrument_key": instrument_key}
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", {}).get(instrument_key, {})
            return data.get("average_price", 0)
    except:
        pass
    return 0

def analyze_options(raw_data, selected_index, target_expiry, vwap_price):
    rows = []
    spot_price = 0
    today_str = datetime.today().strftime('%Y-%m-%d')
    is_expiry_day = (today_str == target_expiry)
    filter_range = 1500 if "SENSEX" in selected_index else 500
    if is_expiry_day:
        min_volume = 100000
        min_oi_drop = 0
        market_status_label = "🔴 EXPIRY DAY MODE - Quantity Aadhi Rakhna | 2:30 ke baad Trade Mat Lena"
    else:
        min_volume = 30000
        min_oi_drop = 5000
        market_status_label = "🔵 NORMAL DAY MODE"
    now = datetime.now()
    candle_closed = True
    if use_candle_lock:
        if now.second > 10:
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
            elif oi_change > 50000 and ltp < close_p:
                signal = "⚠️ AVOID (Theta Decay)"
            else:
                signal = "⏳ WAIT"
            rows.append({"Type": opt_type, "Strike": strike, "LTP (₹)": ltp, "Delta": delta, "Gamma": gamma, "Theta": theta, "Volume": vol, "OI Change": oi_change, "SIGNAL": signal})
    return pd.DataFrame(rows), spot_price, market_status_label, candle_closed

def highlight_signal(val):
    if "GAMMA BLAST" in str(val):
        return 'background-color: #1b5e20; color: white; font-weight: bold;'
    elif "AVOID" in str(val):
        return 'background-color: #b71c1c; color: white;'
    return ''

# --- SOUND FUNCTION - Yehi asli sound hai ---
def play_sound():
    # Web Audio API se andar hi beep banega, koi bahar ki mp3 nahi chahiye
    components.html("""
    <script>
    function beep(freq, start, dur){
        var ctx = new (window.AudioContext || window.webkitAudioContext)();
        var o = ctx.createOscillator();
        var g = ctx.createGain();
        o.connect(g); g.connect(ctx.destination);
        o.frequency.value = freq;
        o.type = 'sine';
        var t = ctx.currentTime + start;
        g.gain.setValueAtTime(0, t);
        g.gain.linearRampToValueAtTime(1, t+0.05);
        g.gain.exponentialRampToValueAtTime(0.001, t+dur);
        o.start(t); o.stop(t+dur+0.1);
    }
    beep(880, 0, 0.4);
    beep(880, 0.5, 0.4);
    beep(880, 1.0, 0.6);
    </script>
    <div style="color:green; font-weight:bold; font-size:18px;">🔔 SOUND BAJ RAHI HAI - SIGNAL AAYA HAI</div>
    """, height=50)
if st.sidebar.button("🔔 Sound Test Karo - Bajake Dekho"):
    play_sound()
if not access_token:
    st.warning("👈 शुरू करने के लिए बाईं तरफ (Sidebar) अपना **Upstox Access Token** और सही **Expiry Date** डालें।")
else:
    raw_data = fetch_upstox_option_chain(access_token, index_choice, expiry_date)
    vwap_val = fetch_vwap(access_token, index_choice)
    if raw_data:
        df, spot, current_mode, candle_closed = analyze_options(raw_data, index_choice, expiry_date, vwap_val)
        st.info(f"⚙️ **स्कैनर मोड:** {current_mode}")
        st.subheader(f"📊 स्पॉट प्राइस: {spot} | VWAP: {vwap_val} | अपडेट समय: {time.strftime('%H:%M:%S')}")
        if not candle_closed:
            st.warning("⏳ Candle Close Lock: Candle abhi band nahi hui hai, signal ke liye candle band hone do...")
        if not df.empty:
            signal_df = df[df["SIGNAL"].str.contains("GAMMA BLAST")]
        else:
            signal_df = pd.DataFrame()
        if not signal_df.empty:
            for _, s in signal_df.iterrows():
                st.success(f"🚨 SIGNAL BANA HAI - {s['Strike']} {s['Type']} KO KHARIDO | LTP: {s['LTP (₹)']} | Gamma: {s['Gamma']} | OI Change: {s['OI Change']}")
            # --- YAHAN SOUND BAJEGI ---
            if sound_on:
                play_sound()
            st.write("### ✅ Sirf Signal Wali Strike - Isko Kharid Sakte Ho")
            st.dataframe(signal_df.style.map(highlight_signal, subset=['SIGNAL']), use_container_width=True)
        else:
            st.info("⏳ Abhi Koi Signal Nahi Hai - WAIT Karo")
        with st.expander("Pura Option Chain Dekhna Ho To Yahan Click Karo"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("### 🟢 CALL Options (CE)")
                if not df.empty:
                    ce_df = df[df["Type"] == "CE"].drop(columns=["Type"])
                    st.dataframe(ce_df.style.map(highlight_signal, subset=['SIGNAL']), use_container_width=True)
            with col2:
                st.markdown("### 🔴 PUT Options (PE)")
                if not df.empty:
                    pe_df = df[df["Type"] == "PE"].drop(columns=["Type"])
                    st.dataframe(pe_df.style.map(highlight_signal, subset=['SIGNAL']), use_container_width=True)
    if auto_refresh:
        time.sleep(5)
        st.rerun()