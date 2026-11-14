import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
import requests
from datetime import datetime
import urllib.parse
import time

# --- Page Settings ---
st.set_page_config(page_title="Live AI Market Engine Pro", layout="wide")
st.title("🔬 Advanced AI Market Intelligence Dashboard (Optimized)")
st.markdown("### Multi-Timeframe Analysis, SMC & Sideways Market Filter")

# --- Auto Refresh Setup (3 Seconds to avoid Upstox Block) ---
refresh_count = st_autorefresh(
    interval=3000, 
    limit=999999, 
    key="upstox_live_refresh"
)

# --- Instruments Mapping ---
INSTRUMENT_MAP = {
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "NIFTY BANK": "NSE_INDEX|Nifty Bank",
    "BSE SENSEX": "BSE_INDEX|SENSEX",
    "RELIANCE": "NSE_EQ|INE002A01018",
    "SBIN (SBI)": "NSE_EQ|INE062A01020",
    "TATA MOTORS": "NSE_EQ|INE155A01022",
    "GOLD": "MCX_FO|495213",
    "SILVER": "MCX_FO|495214",
    "CRUDEOIL": "MCX_FO|573422",
    "NATURALGAS": "MCX_FO|574319",
}

# --- Sidebar Controls ---
st.sidebar.header("🔑 Upstox Access & Settings")
access_token = st.sidebar.text_input("Enter Upstox Access Token", type="password").strip()
selected_asset = st.sidebar.selectbox("Select Asset to Analyze", list(INSTRUMENT_MAP.keys()))
instrument_token = INSTRUMENT_MAP[selected_asset]

timeframe = st.sidebar.selectbox("Select Timeframe", ["1minute", "3minute", "5minute", "15minute", "30minute"], index=2) # Default 5 min
ml_neighbors = st.sidebar.slider("AI Depth (Neighbors)", min_value=3, max_value=15, value=5)

# --- Candle Countdown Calculations ---
tf_map = {"1minute": 60, "3minute": 180, "5minute": 300, "15minute": 900, "30minute": 1800}
tf_sec = tf_map.get(timeframe, 300)
now_sec = datetime.now().second + datetime.now().minute * 60
sec_left = tf_sec - (now_sec % tf_sec)

st.write(f"🔄 Last Sync: {datetime.now().strftime('%H:%M:%S')} | Asset: {selected_asset} | Timeframe: {timeframe} | ⏳ Next Candle in: {sec_left} sec")

if not access_token:
    st.warning("⚠️ Pehle sidebar me Token daalo, tabhi data aayega. Token khali hai abhi.")
    st.stop()

if st.button("🔄 Manual Refresh"):
    st.rerun()

# --- Fetch Data Function ---
def fetch_upstox_intraday_data(token, inst_token, interval):
    encoded_inst_token = urllib.parse.quote(inst_token, safe='')
    url = f"https://upstox.com{encoded_inst_token}/{interval}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            st.error(f"❌ Server Error: {response.status_code}")
            return None
        data = response.json()
        if data.get("status") == "success" and data.get("data") and data["data"].get("candles"):
            candles = data["data"]["candles"]
            df = pd.DataFrame(candles, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'OI'])
            df = df.iloc[::-1].reset_index(drop=True)
            for col in ['Open', 'High', 'Low', 'Close', 'Volume', 'OI']:
                df[col] = df[col].astype(float)
            return df
        else:
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

# --- Smart Money Concepts (SMC) Metrics ---
def calculate_smc_metrics(df):
    if df is None or len(df) < 5:
        return df, [], [], []
    df = df.copy()
    fvg_zones = []
    order_blocks = []
    structure_breaks = []
    
    df['Highest_5'] = df['High'].rolling(window=5, center=True).max()
    df['Lowest_5'] = df['Low'].rolling(window=5, center=True).min()
    
    for i in range(2, len(df) - 2):
        # Fair Value Gaps (FVG)
        if df['High'].iloc[i-2] < df['Low'].iloc[i]:
            gap_size = df['Low'].iloc[i] - df['High'].iloc[i-2]
            if gap_size > (df['Close'].iloc[i] * 0.0002):
                fvg_zones.append({"Type": "Bullish FVG (Imbalance)", "Price_Range": f"₹{df['High'].iloc[i-2]:.2f} - ₹{df['Low'].iloc[i]:.2f}", "Status": "Active"})
        elif df['Low'].iloc[i-2] > df['High'].iloc[i]:
            gap_size = df['Low'].iloc[i-2] - df['High'].iloc[i]
            if gap_size > (df['Close'].iloc[i] * 0.0002):
                fvg_zones.append({"Type": "Bearish FVG (Imbalance)", "Price_Range": f"₹{df['High'].iloc[i]:.2f} - ₹{df['Low'].iloc[i-2]:.2f}", "Status": "Active"})
        
        # Order Blocks (OB)
        if df['Close'].iloc[i] > df['Open'].iloc[i] and (df['Close'].iloc[i] - df['Open'].iloc[i]) > (df['Close'].iloc[i]*0.001):
            if df['Close'].iloc[i-1] < df['Open'].iloc[i-1]:
                order_blocks.append({"Type": "Bullish Order Block (Demand)", "Zone": f"₹{df['Low'].iloc[i-1]:.2f} - ₹{df['High'].iloc[i-1]:.2f}", "Timestamp": df['Timestamp'].iloc[i-1]})
        elif df['Close'].iloc[i] < df['Open'].iloc[i] and (df['Open'].iloc[i] - df['Close'].iloc[i]) > (df['Close'].iloc[i]*0.001):
            if df['Close'].iloc[i-1] > df['Open'].iloc[i-1]:
                order_blocks.append({"Type": "Bearish Order Block (Supply)", "Zone": f"₹{df['Low'].iloc[i-1]:.2f} - ₹{df['High'].iloc[i-1]:.2f}", "Timestamp": df['Timestamp'].iloc[i-1]})
        
        # Market Structure (BOS / CHoCH)
        if df['Close'].iloc[i] > df['High'].iloc[i-1] and df['High'].iloc[i-1] == df['Highest_5'].iloc[i-1]:
            structure_breaks.append({"Type": "BOS (Break of Structure)", "Detail": "Bullish Expansion", "Price": df['Close'].iloc[i]})
        elif df['Close'].iloc[i] < df['Low'].iloc[i-1] and df['Low'].iloc[i-1] == df['Lowest_5'].iloc[i-1]:
            structure_breaks.append({"Type": "CHoCH (Change of Character)", "Detail": "Bearish Shift", "Price": df['Close'].iloc[i]})
            
    return df, fvg_zones, order_blocks, structure_breaks

# --- Optimized AI/ML Engine with Sideways Filter ---
def run_advanced_ml_engine_optimized(df, neighbors):
    if df is None or len(df) < 20:
        return None, 0.0, None, "WAIT (Loading Candles)"
    
    df = df.copy()
    
    # Technical Indicators For Calculations
    df['Returns'] = df['Close'].pct_change()
    df['High_Low_Spread'] = (df['High'] - df['Low']) / df['Close']
    df['Momentum_Rate'] = df['Close'] - df['Close'].shift(5)
    
    # ATR Calculation (Average True Range to measure volatility)
    df['TR'] = np.maximum(df['High'] - df['Low'], 
                          np.maximum(abs(df['High'] - df['Close'].shift(1)), 
                                     abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(window=14).mean()
    df['Vol_MA'] = df['Volume'].rolling(window=10).mean()
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. SIDEWAYS MARKET FILTER LOGIC
    # Agar volume 10-period average ke 80% se kam hai, ya price ATR range se choti hai
    is_sideways = (latest['Volume'] < latest['Vol_MA'] * 0.8) or (latest['High_Low_Spread'] < (latest['ATR'] / latest['Close']))
    
    if is_sideways:
        return 0, 50.0, float(latest['Close']), "❌ SIDEWAYS (NO TRADE)"

    # 2. MACHINE LEARNING ENGINE (Runs only if market is trending)
    df.dropna(inplace=True)
    if len(df) < neighbors + 5:
        return None, 0.0, float(latest['Close']), "WAIT (Collecting Data)"
        
    df['Directional_Shift'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
    features = ['Returns', 'High_Low_Spread', 'Momentum_Rate']
    
    X = df[features].iloc[:-1]
    y = df['Directional_Shift'].iloc[:-1]
    
    clf = KNeighborsClassifier(n_neighbors=neighbors, weights='distance', metric='euclidean')
    clf.fit(X, y)
    
    latest_live_features = df[features].iloc[[-1]]
    predicted_signal = int(clf.predict(latest_live_features)[0])
    prob_scores = clf.predict_proba(latest_live_features)
    confidence_level = float(prob_scores[0][predicted_signal] * 100)
    
    # 3. LIVE WICK REJECTION LOGIC (Your Logic)
    body_size = abs(latest['Close'] - latest['Open'])
    lower_wick = latest['Open'] - latest['Low'] if latest['Close'] > latest['Open'] else latest['Close'] - latest['Low']
    upper_wick = latest['High'] - latest['Close'] if latest['Close'] > latest['Open'] else latest['High'] - latest['Open']
    
    early_signal = "🎯 ANALYSIS RUNNING"
    # Strong lower wick rejection at support
    if lower_wick > body_size * 1.5 and latest['Close'] > prev['Close']:
        early_signal = "🔥 BULLISH REJECTION (CALL SIDE SIGHT)"
    # Strong upper wick rejection at resistance
    elif upper_wick > body_size * 1.5 and latest['Close'] < prev['Close']:
        early_signal = "🔥 BEARISH REJECTION (PUT SIDE SIGHT)"
    elif predicted_signal == 1:
        early_signal = "📈 MOMENTUM: BUY/BULLISH"
    elif predicted_signal == 0:
        early_signal = "📉 MOMENTUM: SELL/BEARISH"
        
    return predicted_signal, confidence_level, float(latest['Close']), early_signal

# --- Main Dashboard Execution ---
raw_feed = fetch_upstox_intraday_data(access_token, instrument_token, timeframe)

if raw_feed is not None:
    processed_df, fvg_list, ob_list, struct_list = calculate_smc_metrics(raw_feed)
    signal, confidence, current_market_price, early_signal = run_advanced_ml_engine_optimized(raw_feed, ml_neighbors)
    
    # Display Top Metrics
    m_col1, m_col2, m_col3 = st.columns(3)
    
    with m_col1:
        st.metric(label="Live Market Price", value=f"₹{current_market_price:.2f}" if current_market_price else "Loading...")
        
    with m_col2:
        if "SIDEWAYS" in early_signal:
            st.error("🚨 Filter Status: NO TRADE ZONE")
        elif "BULLISH" in early_signal or "BUY" in early_signal:
            st.success("🟢 Filter Status: BULLISH MODE")
        elif "BEARISH" in early_signal or "SELL" in early_signal:
            st.danger("🔴 Filter Status: BEARISH MODE")
        else:
            st.warning("🟡 Filter Status: SCROLLING DATA")
            
    with m_col3:
    pass  # Acts as a temporary placeholder

