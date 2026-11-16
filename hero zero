import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

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

# FIX 1: सही Upstox API URL
def fetch_upstox_option_chain(token, instrument_key, expiry):
    url = "https://api.upstox.com/v2/option/chain"
    params = {
        "instrument_key": instrument_key,
        "expiry_date": expiry
    }
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
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

# डेटा प्रोसेस करने और सिग्नल बनाने का फंक्शन - तेरा लॉजिक same है
def analyze_options(raw_data, selected_index, target_expiry):
    rows = []
    spot_price = 0
    
    today_str = datetime.today().strftime('%Y-%m-%d')
    is_expiry_day = (today_str == target_expiry)
    
    filter_range = 1500 if "SENSEX" in selected_index else 500
    
    if is_expiry_day:
        min_volume = 100000
        min_oi_drop = 0
        market_status_label = "🔴 EXPIRY DAY MODE (High Volume Filter)"
    else:
        min_volume = 30000
        min_oi_drop = 5000
        market_status_label = "🔵 NORMAL DAY MODE (Low Volume Filter)"
    
    for item in raw_data:
        # FIX 2: Spot Price ek baar hi lo, har baar overwrite mat karo
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
            
            # --- तेरा डायनामिक सिग्नल लॉजिक - same hai ---
            cond_delta = 0.30 <= abs(delta) <= 0.55
            
            # FIX 3: Gamma ko bhi signal me joda, warna GAMMA BLAST naam ka matlab nahi tha
            cond_gamma = gamma > 0.0005
            
            if is_expiry_day:
                cond_oi = oi_change < 0
                cond_momentum = (vol > min_volume) and (ltp > close_p)
            else:
                cond_oi = oi_change < -min_oi_drop or (oi_change < 0 and abs(oi_change) > (oi * 0.02))
                cond_momentum = (vol > min_volume) and (ltp > close_p)
            
            if cond_delta and cond_gamma and cond_oi and cond_momentum:
                signal = f"🔥 GAMMA BLAST BUY ({opt_type})"
            elif oi_change > 50000 and ltp < close_p:
                signal = "⚠️ AVOID (Theta Decay)"
            else:
                signal = "⏳ WAIT"
                
            rows.append({
                "Type": opt_type,
                "Strike": strike,
                "LTP (₹)": ltp,
                "Delta": delta,
                "Gamma": gamma,
                "Theta": theta,
                "Volume": vol,
                "OI Change": oi_change,
                "SIGNAL": signal
            })
            
    return pd.DataFrame(rows), spot_price, market_status_label

def highlight_signal(val):
    if "GAMMA BLAST" in str(val):
        return 'background-color: #1b5e20; color: white; font-weight: bold;'
    elif "AVOID" in str(val):
        return 'background-color: #b71c1c; color: white;'
    return ''

if not access_token:
    st.warning("👈 शुरू करने के लिए बाईं तरफ (Sidebar) अपना **Upstox Access Token** और सही **Expiry Date** डालें।")
else:
    raw_data = fetch_upstox_option_chain(access_token, index_choice, expiry_date)
    
    if raw_data:
        df, spot, current_mode = analyze_options(raw_data, index_choice, expiry_date)
        
        st.info(f"⚙️ **स्कैनर मोड:** {current_mode}")
        st.subheader(f"📊 स्पॉट प्राइस: {spot} | अपडेट समय: {time.strftime('%H:%M:%S')}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🟢 CALL Options (CE)")
            if not df.empty:
                ce_df = df[df["Type"] == "CE"].drop(columns=["Type"])
                st.dataframe(ce_df.style.map(highlight_signal, subset=['SIGNAL']), use_container_width=True)
            else:
                st.info("डेटा उपलब्ध नहीं है।")
        with col2:
            st.markdown("### 🔴 PUT Options (PE)")
            if not df.empty:
                pe_df = df[df["Type"] == "PE"].drop(columns=["Type"])
                st.dataframe(pe_df.style.map(highlight_signal, subset=['SIGNAL']), use_container_width=True)
            else:
                st.info("डेटा उपलब्ध नहीं है।")

    # FIX 4: while True हटाया, Streamlit wala refresh lagaya - ab freeze nahi hoga
    if auto_refresh:
        time.sleep(5)
        st.rerun()