import streamlit as st
import pandas as pd
import numpy as np
import math
import datetime as dt
import time
from kiteconnect import KiteConnect

# =========================================================
# PAGE
# =========================================================
st.set_page_config(
    page_title="NIFTY SMART TECHNICAL DASHBOARD",
    page_icon="📈",
    layout="wide"
)

st.title("📈 NIFTY SMART TECHNICAL DASHBOARD")
st.caption("Zerodha Kite Connect • Live Market Data")

# =========================================================
# SECRETS
# =========================================================
API_KEY = st.secrets.get("KITE_API_KEY", "")
API_SECRET = st.secrets.get("KITE_API_SECRET", "")

if not API_KEY or not API_SECRET:
    st.error("KITE_API_KEY / KITE_API_SECRET Streamlit Secrets में नहीं मिले।")
    st.stop()

# =========================================================
# SESSION
# =========================================================
if "kite" not in st.session_state:
    st.session_state.kite = None

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "option_snapshot" not in st.session_state:
    st.session_state.option_snapshot = {}

# =========================================================
# KITE LOGIN
# =========================================================
kite = KiteConnect(api_key=API_KEY)

request_token = st.query_params.get("request_token", "")

if request_token:

    try:
        session_data = kite.generate_session(
            request_token,
            api_secret=API_SECRET
        )

        st.session_state.access_token = session_data["access_token"]
        st.session_state.kite = kite
        st.session_state.logged_in = True

        st.query_params.clear()
        st.rerun()

    except Exception as e:
        st.error(f"Zerodha Login Error: {e}")
        st.stop()

if st.session_state.access_token:

    kite.set_access_token(
        st.session_state.access_token
    )

    st.session_state.kite = kite
    st.session_state.logged_in = True

# =========================================================
# LOGIN
# =========================================================
if not st.session_state.logged_in:

    st.warning("🟡 Zerodha Login Required")

    st.link_button(
        "🔐 Login with Zerodha",
        kite.login_url()
    )

    st.stop()

# =========================================================
# CONNECTION
# =========================================================
try:

    profile = kite.profile()

    st.success(
        f"🟢 Zerodha Connected — "
        f"{profile.get('user_name', 'User')}"
    )

    st.caption(
        f"User ID: {profile.get('user_id', '-')}"
    )

except Exception as e:

    st.error(f"Zerodha connection error: {e}")
    st.stop()

# =========================================================
# TIME
# =========================================================
now = dt.datetime.now()

st.caption(
    f"Last Update: {now.strftime('%d-%m-%Y %H:%M:%S')}"
)

# =========================================================
# HELPERS
# =========================================================
def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        return float(value)

    except:

        return default


def calculate_rsi(series, period=14):

    series = pd.Series(series).astype(float)

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss.replace(
        0,
        np.nan
    )

    return 100 - (100 / (1 + rs))


def normal_cdf(x):

    return 0.5 * (
        1 + math.erf(
            x / math.sqrt(2)
        )
    )


def calculate_iv(
    price,
    spot,
    strike,
    time_years,
    option_type,
    rate=0.065
):

    price = safe_float(price)
    spot = safe_float(spot)
    strike = safe_float(strike)

    if price <= 0 or spot <= 0 or strike <= 0:
        return np.nan

    if time_years <= 0:
        return np.nan

    intrinsic = (
        max(spot - strike, 0)
        if option_type == "CE"
        else
        max(strike - spot, 0)
    )

    if price <= intrinsic:
        return np.nan

    def option_price(vol):

        if vol <= 0:
            return intrinsic

        d1 = (
            math.log(spot / strike)
            + (rate + 0.5 * vol * vol)
            * time_years
        ) / (
            vol * math.sqrt(time_years)
        )

        d2 = d1 - vol * math.sqrt(time_years)

        if option_type == "CE":

            return (
                spot * normal_cdf(d1)
                -
                strike
                * math.exp(-rate * time_years)
                * normal_cdf(d2)
            )

        return (
            strike
            * math.exp(-rate * time_years)
            * normal_cdf(-d2)
            -
            spot * normal_cdf(-d1)
        )

    low = 0.0001
    high = 5.0

    try:

        for _ in range(60):

            mid = (
                low + high
            ) / 2

            value = option_price(mid)

            if value > price:
                high = mid
            else:
                low = mid

        return (
            (low + high) / 2
        ) * 100

    except:

        return np.nan


def calculate_pcr(df):

    if df.empty:
        return np.nan

    ce_oi = df.loc[
        df["type"] == "CE",
        "oi"
    ].sum()

    pe_oi = df.loc[
        df["type"] == "PE",
        "oi"
    ].sum()

    if ce_oi <= 0:
        return np.nan

    return pe_oi / ce_oi


def calculate_max_pain(df):

    if df.empty:
        return np.nan

    strikes = sorted(
        df["strike"].unique()
    )

    if not strikes:
        return np.nan

    result = []

    for settlement in strikes:

        pain = 0

        for _, row in df.iterrows():

            strike = row["strike"]
            oi = row["oi"]

            if row["type"] == "CE":

                intrinsic = max(
                    settlement - strike,
                    0
                )

            else:

                intrinsic = max(
                    strike - settlement,
                    0
                )

            pain += (
                intrinsic * oi
            )

        result.append(
            [settlement, pain]
        )

    result_df = pd.DataFrame(
        result,
        columns=["strike", "pain"]
    )

    return result_df.loc[
        result_df["pain"].idxmin(),
        "strike"
    ]


# =========================================================
# MARKET OVERVIEW
# =========================================================
try:

    market_quotes = kite.quote([
        "NSE:NIFTY 50",
        "NSE:NIFTY BANK",
        "NSE:INDIA VIX"
    ])

except Exception as e:

    st.error(
        f"Market quote error: {e}"
    )

    st.stop()


nifty_quote = market_quotes.get(
    "NSE:NIFTY 50",
    {}
)

bank_quote = market_quotes.get(
    "NSE:NIFTY BANK",
    {}
)

vix_quote = market_quotes.get(
    "NSE:INDIA VIX",
    {}
)

nifty_price = safe_float(
    nifty_quote.get("last_price")
)

bank_price = safe_float(
    bank_quote.get("last_price")
)

vix_price = safe_float(
    vix_quote.get("last_price")
)

# =========================================================
# MARKET OVERVIEW
# =========================================================
st.subheader("📊 LIVE MARKET OVERVIEW")

a, b, c, d = st.columns(4)

with a:
    st.metric(
        "NIFTY 50",
        f"{nifty_price:,.2f}"
    )

with b:
    st.metric(
        "BANKNIFTY",
        f"{bank_price:,.2f}"
    )

with c:
    st.metric(
        "INDIA VIX",
        f"{vix_price:,.2f}"
    )

with d:
    st.metric(
        "MARKET STATUS",
        "LIVE"
    )

# =========================================================
# NFO INSTRUMENTS
# =========================================================
@st.cache_data(ttl=300)
def load_nfo():

    return pd.DataFrame(
        kite.instruments("NFO")
    )


nfo = load_nfo()

if nfo.empty:

    st.error(
        "NFO instruments load नहीं हुए।"
    )

    st.stop()

# =========================================================
# FUTURES
# =========================================================
def find_future(name):

    df = nfo[
        (nfo["name"] == name)
        &
        (nfo["instrument_type"] == "FUT")
    ].copy()

    if df.empty:
        return None

    df["expiry"] = pd.to_datetime(
        df["expiry"]
    )

    today = pd.Timestamp(
        dt.date.today()
    )

    df = df[
        df["expiry"] >= today
    ]

    if df.empty:
        return None

    return df.sort_values(
        "expiry"
    ).iloc[0]


nifty_future = find_future(
    "NIFTY"
)

bank_future = find_future(
    "BANKNIFTY"
)

# =========================================================
# HISTORICAL TECHNICAL
# =========================================================
def get_technical(
    token,
    current_price
):

    try:

        today = dt.date.today()

        start = dt.datetime.combine(
            today,
            dt.time(9, 15)
        )

        end = dt.datetime.now()

        candles = kite.historical_data(
            int(token),
            start,
            end,
            "5minute"
        )

        df = pd.DataFrame(
            candles
        )

    except:

        return {
            "price": current_price,
            "rsi": np.nan,
            "vwap": np.nan,
            "volume": 0,
            "ema9": np.nan,
            "ema20": np.nan,
            "ema50": np.nan,
            "ema200": np.nan
        }

    if df.empty:

        return {
            "price": current_price,
            "rsi": np.nan,
            "vwap": np.nan,
            "volume": 0,
            "ema9": np.nan,
            "ema20": np.nan,
            "ema50": np.nan,
            "ema200": np.nan
        }

    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

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

    df["rsi"] = calculate_rsi(
        df["close"]
    )

    typical = (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3

    volume_sum = df["volume"].cumsum()

    if volume_sum.iloc[-1] > 0:

        vwap = (
            typical * df["volume"]
        ).cumsum().iloc[-1] / volume_sum.iloc[-1]

    else:

        vwap = np.nan

    return {
        "price": current_price,
        "rsi": safe_float(
            df["rsi"].iloc[-1],
            np.nan
        ),
        "vwap": safe_float(
            vwap,
            np.nan
        ),
        "volume": safe_float(
            df["volume"].iloc[-1]
        ),
        "ema9": safe_float(
            df["ema9"].iloc[-1],
            np.nan
        ),
        "ema20": safe_float(
            df["ema20"].iloc[-1],
            np.nan
        ),
        "ema50": safe_float(
            df["ema50"].iloc[-1],
            np.nan
        ),
        "ema200": safe_float(
            df["ema200"].iloc[-1],
            np.nan
        )
    }


def future_data(row):

    if row is None:

        return {
            "price": 0,
            "rsi": np.nan,
            "vwap": np.nan,
            "volume": 0,
            "ema9": np.nan,
            "ema20": np.nan,
            "ema50": np.nan,
            "ema200": np.nan
        }

    symbol = row["tradingsymbol"]

    key = f"NFO:{symbol}"

    try:

        q = kite.quote([key])

        quote = q.get(
            key,
            {}
        )

        price = safe_float(
            quote.get("last_price")
        )

    except:

        price = 0

    return get_technical(
        row["instrument_token"],
        price
    )


nifty_tech = future_data(
    nifty_future
)

bank_tech = future_data(
    bank_future
)

# =========================================================
# TECHNICAL DISPLAY
# =========================================================
st.subheader("📈 TECHNICAL ANALYSIS")


def signal(
    rsi,
    price,
    vwap
):

    if pd.isna(rsi) or pd.isna(vwap):
        return "🟡 NO TRADE"

    if rsi > 60 and price > vwap:
        return "🟢 BUY"

    if rsi < 40 and price < vwap:
        return "🔴 SELL"

    return "🟡 NO TRADE"


def show_technical(
    title,
    data,
    future
):

    st.markdown(
        f"### {title}"
    )

    if future is not None:

        st.write(
            f"Futures: **{future['tradingsymbol']}**"
        )

    x, y = st.columns(2)

    with x:

        st.metric(
            "Price",
            f"{data['price']:,.2f}"
        )

        st.metric(
            "RSI (14)",
            "N/A"
            if pd.isna(data["rsi"])
            else f"{data['rsi']:.2f}"
        )

        st.metric(
            "Futures VWAP",
            "N/A"
            if pd.isna(data["vwap"])
            else f"{data['vwap']:,.2f}"
        )

        st.metric(
            "Volume",
            f"{data['volume']:,.0f}"
        )

    with y:

        for name in [
            "ema9",
            "ema20",
            "ema50",
            "ema200"
        ]:

            st.metric(
                name.upper().replace(
                    "EMA",
                    "EMA "
                ),
                "N/A"
                if pd.isna(data[name])
                else f"{data[name]:,.2f}"
            )

    st.write(
        f"Signal Engine: **{signal(data['rsi'], data['price'], data['vwap'])}**"
    )


left, right = st.columns(2)

with left:

    show_technical(
        "NIFTY",
        nifty_tech,
        nifty_future
    )

with right:

    show_technical(
        "BANKNIFTY",
        bank_tech,
        bank_future
    )

# =========================================================
# OPTION CHAIN
# =========================================================
st.subheader("📊 NIFTY OPTION CHAIN")

options = nfo[
    (nfo["name"] == "NIFTY")
    &
    (nfo["instrument_type"].isin([
        "CE",
        "PE"
    ]))
].copy()

options["expiry"] = pd.to_datetime(
    options["expiry"]
)

today = pd.Timestamp(
    dt.date.today()
)

options = options[
    options["expiry"] >= today
]

if options.empty:

    st.error(
        "NIFTY options नहीं मिले।"
    )

    st.stop()

expiries = sorted(
    options["expiry"].dt.date.unique()
)

expiry = st.selectbox(
    "NIFTY Expiry",
    expiries
)

expiry_options = options[
    options["expiry"].dt.date == expiry
].copy()

# =========================================================
# ATM
# =========================================================
spot = nifty_price

atm = round(
    spot / 50
) * 50

st.write(
    f"**NIFTY Spot:** {spot:,.2f}"
)

st.write(
    f"**ATM Strike:** {atm:,.0f}"
)

display_strikes = [
    atm + (i * 50)
    for i in range(-3, 4)
]

# =========================================================
# IMPORTANT:
# FETCH ONLY ATM ±3 LIVE QUOTES
# =========================================================
atm_options = expiry_options[
    expiry_options["strike"].isin(
        display_strikes
    )
].copy()

quote_keys = []

for _, row in atm_options.iterrows():

    quote_keys.append(
        f"NFO:{row['tradingsymbol']}"
    )

# Remove duplicates
quote_keys = list(
    dict.fromkeys(
        quote_keys
    )
)

live_quotes = {}

if quote_keys:

    try:

        # One request = max 500 instruments
        live_quotes = kite.quote(
            quote_keys
        )

    except Exception as e:

        st.error(
            f"Option live quote error: {e}"
        )

# =========================================================
# BUILD ATM ±3 DATA
# =========================================================
rows = []

snapshot_key = (
    expiry.strftime("%Y-%m-%d")
)

old_snapshot = st.session_state.option_snapshot.get(
    snapshot_key,
    {}
)

new_snapshot = {}

for _, row in atm_options.iterrows():

    symbol = row["tradingsymbol"]

    key = f"NFO:{symbol}"

    q = live_quotes.get(
        key,
        {}
    )

    # Direct Kite fields
    ltp = safe_float(
        q.get("last_price")
    )

    volume = safe_float(
        q.get("volume")
    )

    oi = safe_float(
        q.get("oi")
    )

    # -----------------------------------------------------
    # Previous snapshot
    # -----------------------------------------------------
    old = old_snapshot.get(
        symbol
    )

    oi_change = np.nan
    volume_change = np.nan

    if old:

        old_oi = safe_float(
            old.get("oi")
        )

        old_volume = safe_float(
            old.get("volume")
        )

        if old_oi > 0:

            oi_change = (
                (oi - old_oi)
                / old_oi
            ) * 100

        if old_volume > 0:

            volume_change = (
                (volume - old_volume)
                / old_volume
            ) * 100

    new_snapshot[symbol] = {
        "oi": oi,
        "volume": volume
    }

    # -----------------------------------------------------
    # IV
    # -----------------------------------------------------
    expiry_dt = dt.datetime.combine(
        expiry,
        dt.time(15, 30)
    )

    seconds = (
        expiry_dt
        - dt.datetime.now()
    ).total_seconds()

    time_years = max(
        seconds / (
            365 * 24 * 60 * 60
        ),
        0.000001
    )

    iv = calculate_iv(
        ltp,
        spot,
        float(row["strike"]),
        time_years,
        row["instrument_type"]
    )

    rows.append({

        "Strike": float(
            row["strike"]
        ),

        "Type": row["instrument_type"],

        "Symbol": symbol,

        "LTP": ltp,

        "OI": oi,

        "OI Chg %": oi_change,

        "Volume": volume,

        "Vol Chg %": volume_change,

        "IV": iv
    })

# Save snapshot
st.session_state.option_snapshot[
    snapshot_key
] = new_snapshot

option_df = pd.DataFrame(
    rows
)

# =========================================================
# DISPLAY CE / PE SIDE BY SIDE
# =========================================================
ce_df = option_df[
    option_df["Type"] == "CE"
].copy()

pe_df = option_df[
    option_df["Type"] == "PE"
].copy()

ce_df = ce_df.rename(
    columns={
        "LTP": "CE LTP",
        "OI": "CE OI",
        "OI Chg %": "CE OI Chg %",
        "Volume": "CE Volume",
        "Vol Chg %": "CE Vol Chg %",
        "IV": "CE IV"
    }
)

pe_df = pe_df.rename(
    columns={
        "LTP": "PE LTP",
        "OI": "PE OI",
        "OI Chg %": "PE OI Chg %",
        "Volume": "PE Volume",
        "Vol Chg %": "PE Vol Chg %",
        "IV": "PE IV"
    }
)

ce_df = ce_df[
    [
        "Strike",
        "CE LTP",
        "CE OI",
        "CE OI Chg %",
        "CE Volume",
        "CE Vol Chg %",
        "CE IV"
    ]
]

pe_df = pe_df[
    [
        "Strike",
        "PE LTP",
        "PE OI",
        "PE OI Chg %",
        "PE Volume",
        "PE Vol Chg %",
        "PE IV"
    ]
]

final_table = pd.merge(
    ce_df,
    pe_df,
    on="Strike",
    how="outer"
)

final_table = final_table.sort_values(
    "Strike"
)

st.dataframe(
    final_table,
    use_container_width=True,
    hide_index=True
)

# =========================================================
# DATA DIAGNOSTIC
# =========================================================
st.subheader("🔎 Option Data Status")

quote_count = len(live_quotes)

non_zero_oi = int(
    (option_df["OI"] > 0).sum()
)

non_zero_volume = int(
    (option_df["Volume"] > 0).sum()
)

d1, d2, d3 = st.columns(3)

with d1:

    st.metric(
        "Live Quotes Received",
        quote_count
    )

with d2:

    st.metric(
        "Contracts with OI",
        f"{non_zero_oi}/{len(option_df)}"
    )

with d3:

    st.metric(
        "Contracts with Volume",
        f"{non_zero_volume}/{len(option_df)}"
    )

if quote_count == 0:

    st.error(
        "Zerodha से ATM ±3 option quotes नहीं मिले।"
    )

elif non_zero_oi == 0:

    st.warning(
        "Quote response मिला है लेकिन OI अभी 0 है। "
        "नीचे raw response diagnostic देखें।"
    )

# =========================================================
# PCR
# =========================================================
option_df["type"] = option_df["Type"]
option_df["oi"] = option_df["OI"]
option_df["volume"] = option_df["Volume"]

pcr = calculate_pcr(
    option_df
)

max_pain = calculate_max_pain(
    option_df
)

m1, m2, m3 = st.columns(3)

with m1:

    st.metric(
        "PCR (ATM ±3)",
        "N/A"
        if pd.isna(pcr)
        else f"{pcr:.2f}"
    )

with m2:

    st.metric(
        "Max Pain (ATM ±3)",
        "N/A"
        if pd.isna(max_pain)
        else f"{max_pain:,.0f}"
    )

with m3:

    st.metric(
        "Expiry",
        expiry.strftime("%d-%m-%Y")
    )

st.caption(
    "OI और Volume Zerodha live quote से लिए जा रहे हैं। "
    "OI/Volume Change % पिछले dashboard snapshot से calculate होते हैं।"
)

st.caption(
    "IV Black-Scholes model calculation है; "
    "यह Zerodha का direct IV field नहीं है।"
)

# =========================================================
# OPTION SIGNAL
# =========================================================
st.subheader("🎯 OPTION SIGNAL ENGINE")

rsi = nifty_tech["rsi"]

if pd.isna(rsi):

    st.info(
        "🟡 RSI data उपलब्ध नहीं है।"
    )

elif rsi > 60:

    st.success(
        f"🟢 BULLISH BIAS — RSI {rsi:.2f}"
    )

elif rsi < 40:

    st.error(
        f"🔴 BEARISH BIAS — RSI {rsi:.2f}"
    )

else:

    st.warning(
        f"🟡 NEUTRAL / NO TRADE — RSI {rsi:.2f}"
    )

# =========================================================
# REFRESH
# =========================================================
st.divider()

refresh = st.selectbox(
    "Refresh Interval",
    [30, 60],
    index=0
)

st.caption(
    f"Dashboard हर {refresh} सेकंड में refresh होगा।"
)

time.sleep(
    refresh
)

st.rerun()
