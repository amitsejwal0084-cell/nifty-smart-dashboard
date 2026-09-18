import streamlit as st
import pandas as pd
import numpy as np
import math
from datetime import datetime, date
from kiteconnect import KiteConnect
from scipy.stats import norm

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="NIFTY Smart Technical Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 NIFTY SMART TECHNICAL DASHBOARD")
st.caption("Zerodha Kite Connect • Live Market Data")

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
    st.error("KITE_API_KEY / KITE_API_SECRET Streamlit Secrets में नहीं मिले।")
    st.stop()

kite = KiteConnect(api_key=API_KEY)

# =========================================================
# ZERODHA LOGIN CALLBACK
# =========================================================
request_token = st.query_params.get("request_token")

if request_token and not st.session_state.access_token:
    try:
        session_data = kite.generate_session(
            request_token,
            api_secret=API_SECRET
        )

        st.session_state.access_token = session_data["access_token"]

        kite.set_access_token(
            st.session_state.access_token
        )

        profile = kite.profile()
        st.session_state.kite_user = profile

        st.query_params.clear()
        st.rerun()

    except Exception as e:
        st.error(f"Zerodha Login Error: {e}")

# =========================================================
# LOGIN
# =========================================================
if not st.session_state.access_token:

    st.warning("🟡 Zerodha credentials अभी configure नहीं हैं।")

    login_url = kite.login_url()

    st.link_button(
        "🔐 LOGIN WITH ZERODHA",
        login_url,
        use_container_width=True
    )

    st.stop()

# =========================================================
# SET ACCESS TOKEN
# =========================================================
kite.set_access_token(
    st.session_state.access_token
)

# =========================================================
# CONNECTION CHECK
# =========================================================
try:

    profile = kite.profile()

    st.success(
        f"🟢 Zerodha Connected — {profile.get('user_name', 'User')}"
    )

    st.caption(
        f"User ID: {profile.get('user_id', '-')}"
    )

except Exception as e:

    st.error(
        f"Zerodha connection failed: {e}"
    )

    if st.button("🔄 Reconnect Zerodha"):

        st.session_state.access_token = None
        st.session_state.kite_user = None

        st.rerun()

    st.stop()

# =========================================================
# REFRESH
# =========================================================
col_refresh, col_time = st.columns([1, 3])

with col_refresh:

    if st.button(
        "🔄 REFRESH DATA",
        use_container_width=True
    ):
        st.rerun()

with col_time:

    st.write(
        f"Last Update: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}"
    )

# =========================================================
# LIVE MARKET OVERVIEW
# =========================================================
st.subheader("📊 LIVE MARKET OVERVIEW")

try:

    market_quotes = kite.quote([
        "NSE:NIFTY 50",
        "NSE:NIFTY BANK",
        "NSE:INDIA VIX"
    ])

    nifty_spot = market_quotes["NSE:NIFTY 50"]["last_price"]
    banknifty_spot = market_quotes["NSE:NIFTY BANK"]["last_price"]
    vix = market_quotes["NSE:INDIA VIX"]["last_price"]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "NIFTY 50",
        f"{nifty_spot:,.2f}"
    )

    c2.metric(
        "BANKNIFTY",
        f"{banknifty_spot:,.2f}"
    )

    c3.metric(
        "INDIA VIX",
        f"{vix:,.2f}"
    )

    c4.metric(
        "MARKET STATUS",
        "LIVE"
    )

except Exception as e:

    st.error(
        f"Market data error: {e}"
    )

    st.stop()

# =========================================================
# TECHNICAL FUNCTIONS
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


def calculate_ema(series, period):

    return series.ewm(
        span=period,
        adjust=False
    ).mean()


# =========================================================
# NIFTY TECHNICAL DATA
# =========================================================
def get_index_technical(
    instrument_token,
    exchange_symbol
):

    try:

        from_date = (
            pd.Timestamp.now() -
            pd.Timedelta(days=7)
        ).strftime("%Y-%m-%d")

        to_date = (
            pd.Timestamp.now()
        ).strftime("%Y-%m-%d")

        candles = kite.historical_data(
            instrument_token,
            from_date,
            to_date,
            "5minute"
        )

        df = pd.DataFrame(candles)

        if df.empty:
            return None

        df["rsi"] = calculate_rsi(
            df["close"],
            14
        )

        df["ema9"] = calculate_ema(
            df["close"],
            9
        )

        df["ema20"] = calculate_ema(
            df["close"],
            20
        )

        df["ema50"] = calculate_ema(
            df["close"],
            50
        )

        df["ema200"] = calculate_ema(
            df["close"],
            200
        )

        latest = df.iloc[-1]

        return {

            "price": float(latest["close"]),

            "rsi": float(
                latest["rsi"]
            ) if not pd.isna(latest["rsi"]) else np.nan,

            "ema9": float(
                latest["ema9"]
            ),

            "ema20": float(
                latest["ema20"]
            ),

            "ema50": float(
                latest["ema50"]
            ),

            "ema200": float(
                latest["ema200"]
            ),

            "volume": float(
                latest.get("volume", 0)
            )

        }

    except Exception as e:

        st.warning(
            f"{exchange_symbol} technical data error: {e}"
        )

        return None


# =========================================================
# TECHNICAL ANALYSIS
# =========================================================
st.subheader("📈 TECHNICAL ANALYSIS")

nifty_technical = get_index_technical(
    256265,
    "NIFTY"
)

bank_technical = get_index_technical(
    260105,
    "BANKNIFTY"
)

def show_technical(
    title,
    data
):

    st.markdown(f"### {title}")

    if not data:

        st.warning(
            "Technical data उपलब्ध नहीं है."
        )

        return

    price = data["price"]
    rsi = data["rsi"]

    if pd.isna(rsi):

        signal = "🟡 NO TRADE"

    elif rsi > 60:

        signal = "🟢 BULLISH CONDITION"

    elif rsi < 40:

        signal = "🔴 BEARISH CONDITION"

    else:

        signal = "🟡 NO TRADE"

    cols = st.columns(8)

    cols[0].metric(
        "Price",
        f"{price:,.2f}"
    )

    cols[1].metric(
        "RSI (14)",
        f"{rsi:.2f}" if not pd.isna(rsi) else "-"
    )

    cols[2].metric(
        "VWAP",
        "N/A"
    )

    cols[3].metric(
        "Volume",
        f"{data['volume']:,.0f}"
    )

    cols[4].metric(
        "EMA 9",
        f"{data['ema9']:,.2f}"
    )

    cols[5].metric(
        "EMA 20",
        f"{data['ema20']:,.2f}"
    )

    cols[6].metric(
        "EMA 50",
        f"{data['ema50']:,.2f}"
    )

    cols[7].metric(
        "EMA 200",
        f"{data['ema200']:,.2f}"
    )

    st.info(
        f"Signal Engine: {signal}"
    )


show_technical(
    "NIFTY",
    nifty_technical
)

show_technical(
    "BANKNIFTY",
    bank_technical
)

# =========================================================
# LOAD NFO INSTRUMENTS
# =========================================================
@st.cache_data(ttl=300)
def load_nfo_instruments():

    instruments = kite.instruments("NFO")

    df = pd.DataFrame(instruments)

    return df


try:

    nfo = load_nfo_instruments()

except Exception as e:

    st.error(
        f"NFO instruments load error: {e}"
    )

    st.stop()

# =========================================================
# NIFTY OPTIONS
# =========================================================
st.subheader("📊 NIFTY OPTION CHAIN")

nifty_options = nfo[
    (nfo["name"] == "NIFTY") &
    (nfo["instrument_type"].isin(["CE", "PE"]))
].copy()

if nifty_options.empty:

    st.error(
        "NIFTY option contracts नहीं मिले।"
    )

    st.stop()

# =========================================================
# EXPIRY
# =========================================================
nifty_options["expiry"] = pd.to_datetime(
    nifty_options["expiry"]
)

today = pd.Timestamp.now().normalize()

future_expiries = sorted(
    nifty_options.loc[
        nifty_options["expiry"] >= today,
        "expiry"
    ].drop_duplicates()
)

if not future_expiries:

    st.error(
        "Future NIFTY expiry नहीं मिली।"
    )

    st.stop()

expiry_options = [
    x.strftime("%d-%m-%Y")
    for x in future_expiries
]

selected_expiry_text = st.selectbox(
    "NIFTY Expiry",
    expiry_options
)

selected_expiry = pd.to_datetime(
    selected_expiry_text,
    format="%d-%m-%Y"
)

expiry_chain = nifty_options[
    nifty_options["expiry"] == selected_expiry
].copy()

# =========================================================
# ATM
# =========================================================
strikes = sorted(
    expiry_chain["strike"].unique()
)

atm_strike = min(
    strikes,
    key=lambda x: abs(
        float(x) - float(nifty_spot)
    )
)

st.write(
    f"**NIFTY Spot:** {nifty_spot:,.2f}"
)

st.write(
    f"**ATM Strike:** {atm_strike:,.0f}"
)

# =========================================================
# GET FULL EXPIRY QUOTES
# =========================================================
expiry_chain["tradingsymbol"] = (
    expiry_chain["tradingsymbol"]
    .astype(str)
)

symbols = [
    "NFO:" + x
    for x in expiry_chain["tradingsymbol"]
]

# Kite quote supports limited instruments per request.
# We process in batches.
def get_quotes_in_batches(
    symbols,
    batch_size=400
):

    result = {}

    for i in range(
        0,
        len(symbols),
        batch_size
    ):

        batch = symbols[
            i:i + batch_size
        ]

        try:

            q = kite.quote(batch)

            result.update(q)

        except Exception as e:

            st.warning(
                f"Option quote batch error: {e}"
            )

    return result


with st.spinner(
    "Live NIFTY option chain loading..."
):

    full_quotes = get_quotes_in_batches(
        symbols
    )

# =========================================================
# BUILD FULL CHAIN DATA
# =========================================================
records = []

for _, row in expiry_chain.iterrows():

    ts = row["tradingsymbol"]

    key = "NFO:" + ts

    q = full_quotes.get(
        key,
        {}
    )

    records.append({

        "strike": float(
            row["strike"]
        ),

        "type": row["instrument_type"],

        "tradingsymbol": ts,

        "instrument_token": row[
            "instrument_token"
        ],

        "ltp": float(
            q.get("last_price", 0) or 0
        ),

        "oi": float(
            q.get("oi", 0) or 0
        ),

        "volume": float(
            q.get("volume", 0) or 0
        )

    })

full_chain = pd.DataFrame(
    records
)

# =========================================================
# BLACK-SCHOLES IV
# =========================================================
def black_scholes_price(
    S,
    K,
    T,
    r,
    sigma,
    option_type
):

    if T <= 0 or sigma <= 0:

        return max(
            0,
            S - K
        ) if option_type == "CE" else max(
            0,
            K - S
        )

    d1 = (
        math.log(S / K)
        + (r + 0.5 * sigma * sigma) * T
    ) / (
        sigma * math.sqrt(T)
    )

    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "CE":

        return (
            S * norm.cdf(d1)
            - K * math.exp(-r * T)
            * norm.cdf(d2)
        )

    else:

        return (
            K * math.exp(-r * T)
            * norm.cdf(-d2)
            - S * norm.cdf(-d1)
        )


def calculate_iv(
    market_price,
    S,
    K,
    T,
    option_type,
    r=0.065
):

    if (
        market_price <= 0
        or S <= 0
        or K <= 0
        or T <= 0
    ):

        return np.nan

    intrinsic = max(
        0,
        S - K
    ) if option_type == "CE" else max(
        0,
        K - S
    )

    if market_price <= intrinsic:
        return np.nan

    low = 0.0001
    high = 5.0

    try:

        for _ in range(100):

            mid = (
                low + high
            ) / 2

            price = black_scholes_price(
                S,
                K,
                T,
                r,
                mid,
                option_type
            )

            if price > market_price:

                high = mid

            else:

                low = mid

        return (
            (low + high) / 2
        ) * 100

    except Exception:

        return np.nan


# =========================================================
# TIME TO EXPIRY
# =========================================================
expiry_datetime = pd.Timestamp(
    selected_expiry
) + pd.Timedelta(
    hours=15,
    minutes=30
)

now = pd.Timestamp.now()

T = max(
    (
        expiry_datetime - now
    ).total_seconds(),
    0
) / (
    365 * 24 * 60 * 60
)

# =========================================================
# CALCULATE IV
# =========================================================
full_chain["iv"] = full_chain.apply(

    lambda row:
        calculate_iv(
            row["ltp"],
            float(nifty_spot),
            float(row["strike"]),
            T,
            row["type"]
        ),

    axis=1
)

# =========================================================
# FULL CHAIN PCR
# =========================================================
total_ce_oi = full_chain.loc[
    full_chain["type"] == "CE",
    "oi"
].sum()

total_pe_oi = full_chain.loc[
    full_chain["type"] == "PE",
    "oi"
].sum()

if total_ce_oi > 0:

    pcr = (
        total_pe_oi /
        total_ce_oi
    )

else:

    pcr = np.nan

# =========================================================
# FULL CHAIN MAX PAIN
# =========================================================
ce_chain = full_chain[
    full_chain["type"] == "CE"
]

pe_chain = full_chain[
    full_chain["type"] == "PE"
]

pain_strikes = sorted(
    full_chain["strike"].unique()
)

max_pain_value = None
minimum_pain = None

for test_strike in pain_strikes:

    call_pain = (
        np.maximum(
            test_strike -
            ce_chain["strike"].values,
            0
        )
        * ce_chain["oi"].values
    ).sum()

    put_pain = (
        np.maximum(
            pe_chain["strike"].values -
            test_strike,
            0
        )
        * pe_chain["oi"].values
    ).sum()

    total_pain = (
        call_pain +
        put_pain
    )

    if (
        minimum_pain is None
        or total_pain < minimum_pain
    ):

        minimum_pain = total_pain
        max_pain_value = test_strike

# =========================================================
# OPTION SUMMARY
# =========================================================
s1, s2, s3, s4 = st.columns(4)

s1.metric(
    "ATM Strike",
    f"{atm_strike:,.0f}"
)

s2.metric(
    "PCR",
    f"{pcr:.2f}" if not pd.isna(pcr) else "-"
)

s3.metric(
    "Max Pain",
    f"{max_pain_value:,.0f}"
    if max_pain_value is not None
    else "-"
)

s4.metric(
    "Expiry",
    selected_expiry_text
)

# =========================================================
# ATM ±3 TABLE
# =========================================================
display_strikes = [
    x for x in strikes
    if abs(
        float(x) - float(atm_strike)
    ) <= 3 * (
        min(
            [
                strikes[i + 1] - strikes[i]
                for i in range(len(strikes) - 1)
            ]
        )
        if len(strikes) > 1
        else 50
    )
]

# Keep closest ATM ±3 actual strikes
sorted_by_distance = sorted(
    strikes,
    key=lambda x: abs(
        float(x) - float(atm_strike)
    )
)

display_strikes = sorted(
    sorted_by_distance[:7]
)

rows = []

for strike in display_strikes:

    ce = full_chain[
        (full_chain["strike"] == strike) &
        (full_chain["type"] == "CE")
    ]

    pe = full_chain[
        (full_chain["strike"] == strike) &
        (full_chain["type"] == "PE")
    ]

    ce_row = (
        ce.iloc[0]
        if not ce.empty
        else None
    )

    pe_row = (
        pe.iloc[0]
        if not pe.empty
        else None
    )

    rows.append({

        "CE LTP":
            ce_row["ltp"]
            if ce_row is not None
            else np.nan,

        "CE OI":
            ce_row["oi"]
            if ce_row is not None
            else 0,

        "CE Volume":
            ce_row["volume"]
            if ce_row is not None
            else 0,

        "CE IV":
            ce_row["iv"]
            if ce_row is not None
            else np.nan,

        "STRIKE":
            strike,

        "PE IV":
            pe_row["iv"]
            if pe_row is not None
            else np.nan,

        "PE Volume":
            pe_row["volume"]
            if pe_row is not None
            else 0,

        "PE OI":
            pe_row["oi"]
            if pe_row is not None
            else 0,

        "PE LTP":
            pe_row["ltp"]
            if pe_row is not None
            else np.nan
    })


option_table = pd.DataFrame(
    rows
)

# =========================================================
# FORMAT DISPLAY
# =========================================================
display_table = option_table.copy()

for col in [
    "CE LTP",
    "PE LTP"
]:

    display_table[col] = display_table[
        col
    ].map(
        lambda x:
            f"{x:,.2f}"
            if pd.notna(x)
            else "-"
    )

for col in [
    "CE OI",
    "CE Volume",
    "PE Volume",
    "PE OI"
]:

    display_table[col] = display_table[
        col
    ].map(
        lambda x:
            f"{x:,.0f}"
            if pd.notna(x)
            else "-"
    )

for col in [
    "CE IV",
    "PE IV"
]:

    display_table[col] = display_table[
        col
    ].map(
        lambda x:
            f"{x:.2f}%"
            if pd.notna(x)
            else "-"
    )

display_table["STRIKE"] = display_table[
    "STRIKE"
].map(
    lambda x:
        f"{x:,.0f}"
)

st.dataframe(
    display_table,
    use_container_width=True,
    hide_index=True
)

# =========================================================
# CURRENT OPTION SIGNAL
# =========================================================
st.subheader("🎯 OPTION SIGNAL ENGINE")

if nifty_technical:

    rsi_value = nifty_technical["rsi"]

    if not pd.isna(rsi_value):

        if rsi_value > 60:

            st.success(
                "🟢 BULLISH CONDITION — RSI > 60"
            )

        elif rsi_value < 40:

            st.error(
                "🔴 BEARISH CONDITION — RSI < 40"
            )

        else:

            st.warning(
                "🟡 NEUTRAL / NO TRADE — RSI 40–60"
            )

# =========================================================
# IMPORTANT NOTE
# =========================================================
st.info(
    "अगले चरण में वास्तविक OI Change %, Volume Change %, "
    "और 30–60 सेकंड auto-refresh जोड़ सकते हैं। "
    "ये values previous live snapshot से calculate की जाएंगी; "
    "कोई simulated data इस्तेमाल नहीं होगा."
)
