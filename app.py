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

# --- MCX CRUDE OIL SETTING ---
st.sidebar.header("🛢️ MCX Crude Oil")
show_crude = st.sidebar.checkbox("Crude Oil Live dikhao", value=True)
crude_key = st.sidebar.text_input("Crude Instrument Key:", value="MCX_FO|CRUDEOIL25NOV19FUT")

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

# --- MCX CRUDE FETCH FUNCTION ---
def fetch_crude(token, crude_instrument_key):
    url = "https://api.upstox.com/v2/market-quote/quotes"
    params = {"instrument_key": crude_instrument_key}
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            d = r.json().get("data", {}).get(crude_instrument_key, {})
            return d.get("last_price", 0), d.get("close_price", 0)
    except:
        pass
    return 0, 0

def analyze_options(raw_data, selected_index, target_expiry, vwap_price):
    rows = []
    spot_price = 0
    today_str = datetime.now(IST).strftime('%Y-%m-%d')
    is_expiry_day = (today_str == target_expiry)