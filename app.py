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

# एसेट मैपिंग सूची
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

# 1. टाइमफ्रेम का विस्तार (1m, 3m, 5m, 15m, 30m)
timeframe = st.sidebar.selectbox("Select Timeframe", ["1minute", "3minute", "5minute", "15minute", "30minute"], index=0)
ml_neighbors = st.sidebar.slider("AI Depth (Neighbors)", min_value=3, max_value=15, value=5)

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

# 2. स्मार्ट मनी कॉन्सेप्ट्स (SMC) इंजन
def calculate_smc_metrics(df):
    if df is None or len(df) < 5:
        return df, [], [], []
        
    df = df.copy()
    fvg_zones = []
    order_blocks = []
    structure_breaks = []
    
    # High/Low स्विंग डिटेक्शन (मार्केट स्ट्रक्चर के लिए)
    df['Highest_5'] = df['High'].rolling(window=5, center=True).max()
    df['Lowest_5'] = df['Low'].rolling(window=5, center=True).min()
    
    for i in range(2, len(df) - 2):
        # A. Fair Value Gap (FVG) / Imbalance डिटेक्शन
        # Bullish FVG (कैंडल 1 का High < कैंडल 3 का Low)
        if df['High'].iloc[i-2] < df['Low'].iloc[i]:
            gap_size = df['Low'].iloc[i] - df['High'].iloc[i-2]
            if gap_size > (df['Close'].iloc[i] * 0.0002): # न्यूनतम थ्रेशोल्ड
                fvg_zones.append({"Type": "Bullish FVG (Imbalance)", "Price_Range": f"₹{df['High'].iloc[i-2]:.2f} - ₹{df['Low'].iloc[i]:.2f}", "Status": "Active"})
        
        # Bearish FVG (कैंडल 1 का Low > कैंडल 3 का High)
        elif df['Low'].iloc[i-2] > df['High'].iloc[i]:
            gap_size = df['Low'].iloc[i-2] - df['High'].iloc[i]
            if gap_size > (df['Close'].iloc[i] * 0.0002):
                fvg_zones.append({"Type": "Bearish FVG (Imbalance)", "Price_Range": f"₹{df['High'].iloc[i]:.2f} - ₹{df['Low'].iloc[i-2]:.2f}", "Status": "Active"})

        # B. Order Blocks (OB) डिटेक्शन (तेज चाल से ठीक पहले की विपरीत कैंडल)
        # Bullish Order Block (तेज अपमूव से पहले की आखिरी सेलिंग कैंडल)
        if df['Close'].iloc[i] > df['Open'].iloc[i] and (df['Close'].iloc[i] - df['Open'].iloc[i]) > (df['Close'].iloc[i]*0.001):
            if df['Close'].iloc[i-1] < df['Open'].iloc[i-1]:
                order_blocks.append({"Type": "Bullish Order Block (Demand)", "Zone": f"₹{df['Low'].iloc[i-1]:.2f} - ₹{df['High'].iloc[i-1]:.2f}", "Timestamp": df['Timestamp'].iloc[i-1]})
        
        # Bearish Order Block (तेज डाउनमूव से पहले की आखिरी बाइंग कैंडल)
        elif df['Close'].iloc[i] < df['Open'].iloc[i] and (df['Open'].iloc[i] - df['Close'].iloc[i]) > (df['Close'].iloc[i]*0.001):
            if df['Close'].iloc[i-1] > df['Open'].iloc[i-1]:
                order_blocks.append({"Type": "Bearish Order Block (Supply)", "Zone": f"₹{df['Low'].iloc[i-1]:.2f} - ₹{df['High'].iloc[i-1]:.2f}", "Timestamp": df['Timestamp'].iloc[i-1]})

        # C. Market Structure (BOS / CHoCH) डिटेक्शन
        if df['Close'].iloc[i] > df['High'].iloc[i-1] and df['High'].iloc[i-1] == df['Highest_5'].iloc[i-1]:
            structure_breaks.append({"Type": "BOS (Break of Structure)", "Detail": "Bullish Expansion", "Price": df['Close'].iloc[i]})
        elif df['Close'].iloc[i] < df['Low'].iloc[i-1] and df['Low'].iloc[i-1] == df['Lowest_5'].iloc[i-1]:
            structure_breaks.append({"Type": "CHoCH (Change of Character)", "Detail": "Bearish Shift", "Price": df['Close'].iloc[i]})
            
    return df, fvg_zones, order_blocks, structure_breaks

def run_advanced_ml_engine(df, neighbors):
    # 3. स्मार्ट एआई फॉलबैक (अगर डेटा कम है तो क्रैश नहीं होगा)
    if df is None or len(df) < 12:
        st.warning(f"⚠️ Live Data kam mila hai (Sirf {len(df) if df is not None else 0} candles). AI Engine ko minimum 12 candles chahiye. Prediction active karne ke liye Live Market Open hone ka wait karein.")
        return None, None, None
        
    df = df.copy()
    df['Returns'] = df['Close'].pct_change()
    df['High_Low_Spread'] = (df['High'] - df['Low']) / df['Close']
    df['Momentum_Rate'] = df['Close'] - df['Close'].shift(3 if len(df) < 30 else 5) # अडेप्टिव शिफ्ट
    
    # अडेप्टिव रोलिंग विंडो (डेटा साइज़ के हिसाब से खुद को एडजस्ट करेगी)
    window_size = 5 if len(df) < 20 else 10
    df['Volatility'] = df['Returns'].rolling(window=window_size).std()
    
    df.dropna(inplace=True)
    
    if len(df) < neighbors + 2:
        st.info("ℹ️ AI training ke liye aur live samples collect kar raha hai...")
        return None, None, float(df['Close'].iloc[-1])
        
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
    # SMC मीट्रिक्स की गणना
    processed_df, fvg_list, ob_list, struct_list = calculate_smc_metrics(raw_feed)
    
    signal, confidence, current_market_price = run_advanced_ml_engine(raw_feed, ml_neighbors)
    
    m_col1, m_col2, m_col3 = st.columns(3)
    with m_col1:
        if current_market_price:
            st.metric(label="Live Price", value=f"₹{current_market_price:.2f}")
        else:
            st.metric(label="Live Price", value="Fetching...")
            
    with m_col2:
        if signal is not None:
            if signal == 1:
                st.markdown("#### 🎯 AI Signal: <span style='color:green; font-weight:bold;'>BUY (Bullish)</span>", unsafe_allow_html=True)
            else:
                st.markdown("#### 🎯 AI Signal: <span style='color:red; font-weight:bold;'>SELL (Bearish)</span>", unsafe_allow_html=True)
        else:
            st.markdown("#### 🎯 AI Signal: <span style='color:orange; font-weight:bold;'>WAIT (Data Loading)</span>", unsafe_allow_html=True)
            
    with m_col3:
        if confidence:
            st.metric(label="AI Confidence", value=f"{confidence:.1f}%")
        else:
            st.metric(label="AI Confidence", value="0.0%")
            
    # 4. प्रो-ग्रेड स्मार्ट मनी कॉन्सेप्ट्स (SMC) डिस्प्ले
    st.markdown("---")
    st.subheader("🐳 Institutional Footprints (Smart Money Concepts)")
    
    smc_tab1, smc_tab2, smc_tab3 = st.tabs(["⚡ Order Blocks (OB)", "🧲 Fair Value Gaps (FVG)", "📉 Market Structure (BOS/CHoCH)"])
    
    with smc_tab1:
        if ob_list:
            st.dataframe(pd.DataFrame(ob_list).tail(5), use_container_width=True)
        else:
            st.info("Abhi koi taza Order Block detect nahi hua hai. Market me heavy volume institutional move ka wait karein.")
            
    with smc_tab2:
        if fvg_list:
            st.dataframe(pd.DataFrame(fvg_list).tail(5), use_container_width=True)
        else:
            st.info("Market balanced hai. Koi active Fair Value Gap (Imbalance) nahi mila.")
            
    with smc_tab3:
        if struct_list:
            st.dataframe(pd.DataFrame(struct_list).tail(5), use_container_width=True)
        else:
