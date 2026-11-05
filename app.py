import streamlit as st
import pandas as pd
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
import requests
from datetime import datetime
import urllib.parse

# 1. पेज सेटअप
st.set_page_config(page_title="Live AI Market Engine", layout="wide")
st.title("🔬 Advanced AI Market Intelligence Dashboard")
st.markdown("### Multi-Timeframe Analysis & Machine Learning (Pure Live Data)")

# 2. फिक्स इंस्ट्रूमेंट की (Instrument Keys)
INSTRUMENT_MAP = {
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "NIFTY BANK": "NSE_INDEX|Nifty Bank",
    "BSE SENSEX": "BSE_INDEX|SENSEX",
    "RELIANCE": "NSE_EQ|INE002A01018",
    "SBIN (SBI)": "NSE_EQ|INE062A01020",
    "TATA MOTORS": "NSE_EQ|INE155A01022"
}

# 3. साइडबार इनपुट
st.sidebar.header("🔑 Upstox Access")
access_token = st.sidebar.text_input("Enter Upstox Access Token", type="password")

selected_asset = st.sidebar.selectbox("Select Asset to Analyze", list(INSTRUMENT_MAP.keys()))
instrument_token = INSTRUMENT_MAP[selected_asset]

# [CHANGED] 5minute hata diya kyuki Upstox Intraday me support nahi karta - 400 error isi se aa raha tha
timeframe = st.sidebar.selectbox("Select Timeframe", ["1minute", "30minute"], index=0)
ml_neighbors = st.sidebar.slider("AI Depth (Neighbors)", min_value=3, max_value=15, value=5)
refresh_interval = st.sidebar.slider("Auto-Refresh (Seconds)", min_value=5, max_value=30, value=10, step=5)

# 4. शुद्ध लाइव अपस्टॉक्स इंट्राडे API (URL ENCODING SECURED)
def fetch_upstox_intraday_data(token, inst_token, interval):
    if not token:
        return None
        
    # [FIXED] safe='' se | aur space dono properly encode honge
    encoded_inst_token = urllib.parse.quote(inst_token, safe='')
    
    base_domain = "https://api." + "upstox.com"
    api_route = "/v2/historical-candle/intraday"
    url = f"{base_domain}{api_route}/{encoded_inst_token}/{interval}"
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            # [CHANGED] Ab Upstox ka asli error message bhi dikhega
            st.error(f"❌ Server Returned HTTP Error: {response.status_code}")
            st.code(response.text[:500])
            return None
            
        data = response.json()
        
        if data.get("errors"):
            st.error(f"❌ Upstox API Error: {data['errors'].get('message')} (Code: {data['errors'].get('errorCode')})")
            return None
            
        if data.get("status") == "success" and data.get("data") and data["data"].get("candles"):
            candles = data["data"]["candles"]
            df = pd.DataFrame(candles, columns=['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'OI'])
            df = df.iloc[::-1].reset_index(drop=True)
            
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = df[col].astype(float)
            return df
            
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"🌐 Network/Connection Error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"💻 Internal Code Crash: {str(e)}")
        return None

# 5. मशीन लर्निंग एल्गोरिदम
def run_advanced_ml_engine(df, neighbors):
    if df is None or len(df) < 30:
        return None, None, None
        
    df['Returns'] = df['Close'].pct_change()
    df['High_Low_Spread'] = (df['High'] - df['Low']) / df['Close']
    df['Momentum_Rate'] = df['Close'] - df['Close'].shift(5)
    df['Volatility'] = df['Returns'].rolling(window=10).std()
    
    df.dropna(inplace=True)
    if len(df) < 10:
        return None, None, None

    df['Directional_Shift'] = np.where(df['Close'].shift(-1) > df['Close'], 1, 0)
    
    features = ['Returns', 'High_Low_Spread', 'Momentum_Rate', 'Volatility']
    X = df[features].iloc[:-1]
    y = df['Directional_Shift'].iloc[:-1]
    
    clf = KNeighborsClassifier(n_neighbors=neighbors, weights='distance', metric='euclidean')
    clf.fit(X, y)
    
    latest_live_features = df[features].iloc[[-1]]
    predicted_signal = clf.predict(latest_live_features)
    
    prob_scores = clf.predict_proba(latest_live_features)
    # [FIXED] Correct confidence extraction
    confidence_level = float(prob_scores[0][predicted_signal[0]] * 100)
    latest_close_price = float(df['Close'].iloc[-1])
        
    return predicted_signal, confidence_level, latest_close_price

# 6. ऑटो रिफ्रेश कंटेनर
st.subheader(f"📊 Live Feed: {selected_asset} ({timeframe.upper()})")

@st.fragment(run_every=refresh_interval)
def refresh_analytics_grid():
    current_time = datetime.now().strftime("%H:%M:%S")
    st.write(f"🔄 लास्ट लाइव सिंक: **{current_time}** (स्पीड: {refresh_interval}s)")
    
    if not access_token:
        st.info("💡 शुरुआत करने के लिए साइडबार में **Upstox Access Token** डालें।")
        return