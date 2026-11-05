import streamlit as st
import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
import requests
from datetime import datetime
import urllib.parse

st.set_page_config(page_title="Live AI Market Engine", layout="wide")
st.title("🔬 Advanced AI Market Intelligence Dashboard")
st.markdown("### Multi-Timeframe Analysis & Machine Learning (Pure Live Data)")

INSTRUMENT_MAP = {
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "NIFTY BANK": "NSE_INDEX|Nifty Bank",
    "BSE SENSEX": "BSE_INDEX|SENSEX",
    "RELIANCE": "NSE_EQ|INE002A01018",
    "SBIN (SBI)": "NSE_EQ|INE062A01020",
    "TATA MOTORS": "NSE_EQ|INE155A01022"
}

st.sidebar.header("🔑 Upstox Access")
access_token = st.sidebar.text_input("Enter Upstox Access Token", type="password").strip()
selected_asset = st.sidebar.selectbox("Select Asset to Analyze", list(INSTRUMENT_MAP.keys()))
instrument_token = INSTRUMENT_MAP[selected_asset]
timeframe = st.sidebar.selectbox("Select Timeframe", ["1minute", "30minute"], index=0)
ml_neighbors = st.sidebar.slider("AI Depth (Neighbors)", min_value=3, max_value=15, value=5)

# DEBUG - Token dala hai ya nahi, yaha dikhega
st.write(f"🔄 Last Sync: {datetime.now().strftime('%H:%M:%S')} | Asset: {selected_asset} | Timeframe: {timeframe}")
if not access_token:
    st.warning("⚠️ Pehle sidebar me Token daalo, tabhi data aayega. Token khali hai abhi.")
    st.stop()

if st.button("🔄 Refresh Live Data"):
    st.rerun()

def fetch_upstox_intraday_data(token, inst_token, interval):
    encoded_inst_token = urllib.parse.quote(inst_token, safe='')
    url = f"https://api.upstox.com/v2/historical-candle/intraday/{encoded_inst_token}/{interval}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        st.write(f"API Status Code: {response.status_code}")
        if response.status_code != 200:
            st.error(f"❌ Server Error: {response.status_code}")
            st.code(response.text[:800])
            return None
        data = response.json()
        if data.get("status") == "success" and data.get("data") and data["data"].get("candles"):
            candles = data["data"]["candles"]
            df = pd.DataFrame(candles, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'OI'])
            df = df.iloc[::-1].reset_index(drop=True)
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = df[col].astype(float)
            return df
        else:
            st.error(f"API se khali data aaya: {str(data)[:500]}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def run_advanced_ml_engine(df, neighbors):
    if df is None or len(df) < 30:
        st.warning(f"Data kam hai, sirf {len(df) if df is not None else 0} candles mili. Market khulne ka wait karo.")
        return None, None, None
    df['Returns'] = df['Close'].pct_change()
    df['High_Low_Spread'] = (df['High'] - df['Low']) / df['Close']
    df['Momentum_Rate'] = df['Close'] - df['Close'].shift(5)
    df['Volatility'] = df['Returns'].rolling(window=10).std()
    df.dropna(inplace=True)
    df['Directional_Shift'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
    features = ['Returns', 'High_Low_Spread', 'Momentum_Rate', 'Volatility']
    X = df[features].iloc[:-1]
    y = df['Directional_Shift'].iloc[:-1]
    clf = KNeighborsClassifier(n_neighbors=neighbors, weights='distance', metric='euclidean')
    clf.fit(X, y)
    latest_live_features = df[features].iloc[[-1]]
    predicted_signal = clf.predict(latest_live_features)
    prob_scores = clf.predict_proba(latest_live_features)
    confidence_level = float(prob_scores[0][predicted_signal[0]] * 100)
    latest_close_price = float(df['Close'].iloc[-1])
    return predicted_signal, confidence_level, latest_close_price

st.subheader(f"📊 Live Feed: {selected_asset} ({timeframe.upper()})")
raw_feed = fetch_upstox_intraday_data(access_token, instrument_token, timeframe)

if raw_feed is not None:
    signal, confidence, current_market_price = run_advanced_ml_engine(raw_feed, ml_neighbors)
    if signal is not None:
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric(label="Live Price", value=f"₹{current_market_price:.2f}")
        with m_col2:
            if signal == 1:
                st.markdown("#### 🎯 AI Signal: <span style='color:green; font-weight:bold;'>BUY (Bullish)</span>", unsafe_allow_html=True)
            else:
                st.markdown("#### 🎯 AI Signal: <span style='color:red; font-weight:bold;'>SELL (Bearish)</span>", unsafe_allow_html=True)
        with m_col3:
            st.metric(label="AI Confidence", value=f"{confidence:.1f}%")
        st.subheader("📝 Live Candle Matrix (Last 5 Logs)")
        st.dataframe(raw_feed[['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']].tail(5), use_container_width=True)