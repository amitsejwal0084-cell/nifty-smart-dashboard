import streamlit as st
from kiteconnect import KiteConnect
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="NIFTY Smart Technical Dashboard",
    page_icon="📈",
    layout="wide"
)

# =========================================================
# SESSION STATE
# =========================================================

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "kite_user" not in st.session_state:
    st.session_state.kite_user = None

# =========================================================
# SECRETS
# =========================================================

try:
    API_KEY = st.secrets["KITE_API_KEY"]
    API_SECRET = st.secrets["KITE_API_SECRET"]

except Exception:
    st.error("❌ Zerodha API credentials configured नहीं हैं.")
    st.info(
        "Streamlit → Manage app → Settings → Secrets में "
        "KITE_API_KEY और KITE_API_SECRET डालें."
    )
    st.stop()

# =========================================================
# KITE
# =========================================================

kite = KiteConnect(api_key=API_KEY)

# =========================================================
# REQUEST TOKEN
# =========================================================

request_token = st.query_params.get("request_token")

if request_token and st.session_state.access_token is None:

    try:
        session_data = kite.generate_session(
            request_token,
            api_secret=API_SECRET
        )

        st.session_state.access_token = session_data["access_token"]

        st.session_state.kite_user = session_data.get(
            "user_name",
            session_data.get("user_id", "Zerodha User")
        )

        st.query_params.clear()

        st.rerun()

    except Exception as e:
        st.error("❌ Zerodha Login / Token Exchange Failed")
        st.code(str(e))

# =========================================================
# HEADER
# =========================================================

st.title("📈 NIFTY Smart Technical Analysis Dashboard")

st.caption(
    "Zerodha Kite Connect • Live Market Analysis"
)

# =========================================================
# CONNECTION
# =========================================================

if not st.session_state.access_token:

    st.warning("🟡 Zerodha अभी connected नहीं है.")

    login_url = kite.login_url()

    st.link_button(
        "🔐 LOGIN WITH ZERODHA",
        login_url,
        use_container_width=True
    )

    st.stop()

# =========================================================
# SET TOKEN
# =========================================================

kite.set_access_token(
    st.session_state.access_token
)

# =========================================================
# CHECK CONNECTION
# =========================================================

try:

    profile = kite.profile()

    st.success(
        f"🟢 Zerodha Connected — "
        f"{profile.get('user_name', 'User')}"
    )

    st.caption(
        f"User ID: {profile.get('user_id', '')}"
    )

except Exception as e:

    st.error("🔴 Access Token invalid या expired है.")
    st.code(str(e))

    st.stop()

# =========================================================
# REFRESH
# =========================================================

col_refresh, col_time = st.columns([1, 4])

with col_refresh:

    if st.button(
        "🔄 Refresh Market Data",
        use_container_width=True
    ):
        st.rerun()

with col_time:

    st.caption(
        "Last Update: "
        + datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    )

# =========================================================
# FUNCTIONS
# =========================================================

def calculate_rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_vwap(df):

    if df.empty:
        return np.nan

    typical_price = (
        df["high"] +
        df["low"] +
        df["close"]
    ) / 3

    cumulative_volume = df["volume"].cumsum()

    cumulative_value = (
        typical_price * df["volume"]
    ).cumsum()

    vwap = (
        cumulative_value /
        cumulative_volume.replace(0, np.nan)
    )

    return vwap.iloc[-1]


def get_analysis(instrument_token):

    try:

        end_date = datetime.now()
        start_date = end_date - timedelta(days=5)

        candles = kite.historical_data(
            instrument_token,
            start_date,
            end_date,
            "5minute",
            continuous=False,
            oi=False
        )

        df = pd.DataFrame(candles)

        if df.empty:
            return None

        df["date"] = pd.to_datetime(df["date"])

        # RSI
        df["rsi"] = calculate_rsi(
            df["close"],
            14
        )

        # EMA
        df["ema9"] = df["close"].ewm(
            span=9,
            adjust=False
        ).mean()

        df["ema20"] = df["close"].ewm(
            span=20,
            adjust=False
        ).mean()

        df["ema50"] = df["close"].ewm(
            span=50,
            adjust=False
        ).mean()

        df["ema200"] = df["close"].ewm(
            span=200,
            adjust=False
        ).mean()

        latest = df.iloc[-1]

        rsi = latest["rsi"]

        vwap = calculate_vwap(df)

        volume = latest["volume"]

        previous_volume = (
            df.iloc[-2]["volume"]
            if len(df) > 1
            else np.nan
        )

        if previous_volume and previous_volume != 0:

            volume_change = (
                (volume - previous_volume)
                / previous_volume
            ) * 100

        else:
            volume_change = np.nan

        # =================================================
        # SIGNAL
        # =================================================

        price = latest["close"]

        if (
            pd.notna(rsi)
            and pd.notna(vwap)
            and rsi > 60
            and price > vwap
        ):

            signal = "🟢 BUY"

        elif (
            pd.notna(rsi)
            and pd.notna(vwap)
            and rsi < 40
            and price < vwap
        ):

            signal = "🔴 SELL"

        else:

            signal = "🟡 NO TRADE"

        return {
            "price": price,
            "rsi": rsi,
            "vwap": vwap,
            "ema9": latest["ema9"],
            "ema20": latest["ema20"],
            "ema50": latest["ema50"],
            "ema200": latest["ema200"],
            "volume": volume,
            "volume_change": volume_change,
            "signal": signal
        }

    except Exception as e:

        return {
            "error": str(e)
        }


# =========================================================
# LIVE QUOTES
# =========================================================

try:

    quotes = kite.quote([
        "NSE:NIFTY 50",
        "NSE:NIFTY BANK",
        "NSE:INDIA VIX"
    ])

except Exception as e:

    st.error("❌ Live market data प्राप्त नहीं हो पाया.")
    st.code(str(e))
    st.stop()

# =========================================================
# MARKET OVERVIEW
# =========================================================

st.divider()

st.header("📊 Market Overview")

col1, col2, col3, col4 = st.columns(4)

nifty_price = quotes["NSE:NIFTY 50"]["last_price"]
bank_price = quotes["NSE:NIFTY BANK"]["last_price"]
vix_price = quotes["NSE:INDIA VIX"]["last_price"]

with col1:

    st.metric(
        "NIFTY 50",
        f"{nifty_price:,.2f}"
    )

with col2:

    st.metric(
        "BANKNIFTY",
        f"{bank_price:,.2f}"
    )

with col3:

    st.metric(
        "INDIA VIX",
        f"{vix_price:,.2f}"
    )

with col4:

    st.metric(
        "Market Status",
        "LIVE 🟢"
    )

# =========================================================
# TECHNICAL ANALYSIS
# =========================================================

st.divider()

st.header("📈 Technical Analysis")

nifty_data = get_analysis(256265)
bank_data = get_analysis(260105)

# =========================================================
# NIFTY
# =========================================================

st.subheader("NIFTY 50")

if nifty_data and "error" not in nifty_data:

    a1, a2, a3, a4 = st.columns(4)

    with a1:
        st.metric(
            "Price",
            f"{nifty_data['price']:,.2f}"
        )

    with a2:

        rsi_value = nifty_data["rsi"]

        st.metric(
            "RSI (14)",
            f"{rsi_value:.2f}"
            if pd.notna(rsi_value)
            else "—"
        )

    with a3:

        st.metric(
            "VWAP",
            f"{nifty_data['vwap']:,.2f}"
            if pd.notna(nifty_data["vwap"])
            else "—"
        )

    with a4:

        st.metric(
            "Volume",
            f"{nifty_data['volume']:,.0f}"
        )

    st.write(
        f"EMA 9: `{nifty_data['ema9']:.2f}`"
    )

    st.write(
        f"EMA 20: `{nifty_data['ema20']:.2f}`"
    )

    st.write(
        f"EMA 50: `{nifty_data['ema50']:.2f}`"
    )

    st.write(
        f"EMA 200: `{nifty_data['ema200']:.2f}`"
    )

    if pd.notna(nifty_data["volume_change"]):

        st.write(
            f"Volume Change: "
            f"`{nifty_data['volume_change']:.2f}%`"
        )

    if nifty_data["signal"] == "🟢 BUY":

        st.success(nifty_data["signal"])

    elif nifty_data["signal"] == "🔴 SELL":

        st.error(nifty_data["signal"])

    else:

        st.warning(nifty_data["signal"])

else:

    st.error(
        nifty_data.get("error", "NIFTY data unavailable")
        if nifty_data
        else "NIFTY data unavailable"
    )

# =========================================================
# BANKNIFTY
# =========================================================

st.subheader("BANKNIFTY")

if bank_data and "error" not in bank_data:

    b1, b2, b3, b4 = st.columns(4)

    with b1:

        st.metric(
            "Price",
            f"{bank_data['price']:,.2f}"
        )

    with b2:

        rsi_value = bank_data["rsi"]

        st.metric(
            "RSI (14)",
            f"{rsi_value:.2f}"
            if pd.notna(rsi_value)
            else "—"
        )

    with b3:

        st.metric(
            "VWAP",
            f"{bank_data['vwap']:,.2f}"
            if pd.notna(bank_data["vwap"])
            else "—"
        )

    with b4:

        st.metric(
            "Volume",
            f"{bank_data['volume']:,.0f}"
        )

    st.write(
        f"EMA 9: `{bank_data['ema9']:.2f}`"
    )

    st.write(
        f"EMA 20: `{bank_data['ema20']:.2f}`"
    )

    st.write(
        f"EMA 50: `{bank_data['ema50']:.2f}`"
    )

    st.write(
        f"EMA 200: `{bank_data['ema200']:.2f}`"
    )

    if pd.notna(bank_data["volume_change"]):

        st.write(
            f"Volume Change: "
            f"`{bank_data['volume_change']:.2f}%`"
        )

    if bank_data["signal"] == "🟢 BUY":

        st.success(bank_data["signal"])

    elif bank_data["signal"] == "🔴 SELL":

        st.error(bank_data["signal"])

    else:

        st.warning(bank_data["signal"])

else:

    st.error(
        bank_data.get("error", "BANKNIFTY data unavailable")
        if bank_data
        else "BANKNIFTY data unavailable"
    )

# =========================================================
# SIGNAL ENGINE
# =========================================================

st.divider()

st.header("🎯 Signal Engine")

s1, s2, s3 = st.columns(3)

with s1:

    st.subheader("NIFTY")

    if nifty_data and "signal" in nifty_data:

        st.write(
            f"Signal: **{nifty_data['signal']}**"
        )

        if pd.notna(nifty_data["rsi"]):

            st.write(
                f"RSI: `{nifty_data['rsi']:.2f}`"
            )

with s2:

    st.subheader("BANKNIFTY")

    if bank_data and "signal" in bank_data:

        st.write(
            f"Signal: **{bank_data['signal']}**"
        )

        if pd.notna(bank_data["rsi"]):

            st.write(
                f"RSI: `{bank_data['rsi']:.2f}`"
            )

with s3:

    st.subheader("Overall Market")

    st.info(
        "Live technical analysis active"
    )

# =========================================================
# OPTION ANALYSIS - NEXT STAGE
# =========================================================

st.divider()

st.header("🔗 Option Market Analysis")

st.info(
    "Option Chain, ATM ±3 strikes, PCR, OI Change, "
    "Volume Change और Max Pain अगले चरण में जोड़े जाएंगे."
)

# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "⚡ Zerodha Kite Connect • Live Market Data • "
    "Technical Analysis"
)
