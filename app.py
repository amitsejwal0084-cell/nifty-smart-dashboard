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
# SESSION STATE
# =========================================================
if "kite" not in st.session_state:
    st.session_state.kite = None

if "access_token" not in st.session_state:
    st.session_state.access_token = None

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "request_token" not in st.session_state:
    st.session_state.request_token = ""

if "option_snapshot" not in st.session_state:
    st.session_state.option_snapshot = {}

if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()

# =========================================================
# LOGIN
# =========================================================
kite = KiteConnect(api_key=API_KEY)

query_params = st.query_params
request_token = query_params.get("request_token", "")

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

# Restore kite object after rerun
if st.session_state.access_token:
    kite.set_access_token(st.session_state.access_token)
    st.session_state.kite = kite
    st.session_state.logged_in = True

# =========================================================
# LOGIN SCREEN
# =========================================================
if not st.session_state.logged_in:

    st.warning("🟡 Zerodha Login Required")

    login_url = kite.login_url()

    st.link_button(
        "🔐 Login with Zerodha",
        login_url
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
    st.session_state.logged_in = False
    st.stop()

# =========================================================
# TIME
# =========================================================
now = dt.datetime.now()

st.caption(
    f"Last Update: {now.strftime('%d-%m-%Y %H:%M:%S')}"
)

# =========================================================
# HELPER FUNCTIONS
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

    rs = avg_gain / avg_loss.replace(0, np.nan)

    rsi = 100 - (100 / (1 + rs))

    return rsi


def normal_cdf(x):

    return 0.5 * (
        1 + math.erf(x / math.sqrt(2))
    )


def black_scholes_iv(
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

    intrinsic = max(
        spot - strike,
        0
    ) if option_type == "CE" else max(
        strike - spot,
        0
    )

    if price <= intrinsic:
        return np.nan

    def option_price(vol):

        if vol <= 0:
            return intrinsic

        d1 = (
            math.log(spot / strike)
            + (rate + 0.5 * vol * vol) * time_years
        ) / (
            vol * math.sqrt(time_years)
        )

        d2 = d1 - vol * math.sqrt(time_years)

        if option_type == "CE":

            return (
                spot * normal_cdf(d1)
                - strike * math.exp(-rate * time_years)
                * normal_cdf(d2)
            )

        else:

            return (
                strike * math.exp(-rate * time_years)
                * normal_cdf(-d2)
                - spot * normal_cdf(-d1)
            )

    low = 0.0001
    high = 5.0

    try:

        for _ in range(60):

            mid = (low + high) / 2

            value = option_price(mid)

            if value > price:
                high = mid
            else:
                low = mid

        return ((low + high) / 2) * 100

    except:

        return np.nan


def calculate_max_pain(chain):

    if chain.empty:
        return np.nan

    strikes = sorted(
        chain["strike"].dropna().unique()
    )

    if not strikes:
        return np.nan

    pain_values = []

    for settlement in strikes:

        total_pain = 0

        for _, row in chain.iterrows():

            strike = safe_float(row["strike"])
            oi = safe_float(row["oi"])

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

            total_pain += intrinsic * oi

        pain_values.append(
            (settlement, total_pain)
        )

    pain_df = pd.DataFrame(
        pain_values,
        columns=["strike", "pain"]
    )

    return pain_df.loc[
        pain_df["pain"].idxmin(),
        "strike"
    ]


def calculate_pcr(chain):

    if chain.empty:
        return np.nan

    ce_oi = chain.loc[
        chain["type"] == "CE",
        "oi"
    ].sum()

    pe_oi = chain.loc[
        chain["type"] == "PE",
        "oi"
    ].sum()

    if ce_oi <= 0:
        return np.nan

    return pe_oi / ce_oi


def chunk_list(items, size=400):

    for i in range(0, len(items), size):
        yield items[i:i + size]


# =========================================================
# GET MARKET QUOTES
# =========================================================

try:

    market_symbols = [
        "NSE:NIFTY 50",
        "NSE:NIFTY BANK",
        "NSE:INDIA VIX"
    ]

    market_quotes = kite.quote(market_symbols)

except Exception as e:

    st.error(f"Market quote error: {e}")
    st.stop()


# =========================================================
# MARKET VALUES
# =========================================================

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

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "NIFTY 50",
        f"{nifty_price:,.2f}"
    )

with c2:
    st.metric(
        "BANKNIFTY",
        f"{bank_price:,.2f}"
    )

with c3:
    st.metric(
        "INDIA VIX",
        f"{vix_price:,.2f}"
    )

with c4:
    st.metric(
        "MARKET STATUS",
        "LIVE"
    )

# =========================================================
# HISTORICAL DATA
# =========================================================

def get_intraday_data(
    instrument_token
):

    today = dt.date.today()

    from_time = dt.datetime.combine(
        today,
        dt.time(9, 15)
    )

    to_time = dt.datetime.now()

    try:

        data = kite.historical_data(
            instrument_token,
            from_time,
            to_time,
            "5minute"
        )

        return pd.DataFrame(data)

    except:

        return pd.DataFrame()


def technical_analysis(
    instrument_token,
    current_price
):

    df = get_intraday_data(
        instrument_token
    )

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

    df["close"] = pd.to_numeric(
        df["close"],
        errors="coerce"
    )

    df["high"] = pd.to_numeric(
        df["high"],
        errors="coerce"
    )

    df["low"] = pd.to_numeric(
        df["low"],
        errors="coerce"
    )

    df["volume"] = pd.to_numeric(
        df["volume"],
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
        df["close"],
        14
    )

    volume = df["volume"]

    typical_price = (
        df["high"]
        + df["low"]
        + df["close"]
    ) / 3

    cumulative_volume = volume.cumsum()

    if cumulative_volume.iloc[-1] > 0:

        vwap = (
            typical_price * volume
        ).cumsum().iloc[-1] / cumulative_volume.iloc[-1]

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


# =========================================================
# FIND NIFTY / BANKNIFTY FUTURES
# =========================================================

@st.cache_data(ttl=300)
def load_nfo_instruments():

    try:

        return pd.DataFrame(
            kite.instruments("NFO")
        )

    except Exception:

        return pd.DataFrame()


nfo = load_nfo_instruments()


def get_nearest_future(
    instruments,
    name
):

    if instruments.empty:
        return None

    df = instruments.copy()

    df = df[
        (df["name"] == name)
        &
        (df["instrument_type"] == "FUT")
    ]

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

    df = df.sort_values(
        "expiry"
    )

    return df.iloc[0]


nifty_future = get_nearest_future(
    nfo,
    "NIFTY"
)

bank_future = get_nearest_future(
    nfo,
    "BANKNIFTY"
)

# =========================================================
# FUTURES TECHNICAL DATA
# =========================================================

def futures_technical(
    future_row
):

    if future_row is None:

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

    token = int(
        future_row["instrument_token"]
    )

    symbol = future_row["tradingsymbol"]

    try:

        q = kite.quote(
            f"NFO:{symbol}"
        )

        quote = q.get(
            f"NFO:{symbol}",
            {}
        )

        price = safe_float(
            quote.get("last_price")
        )

    except:

        price = 0

    result = technical_analysis(
        token,
        price
    )

    return result


nifty_fut_tech = futures_technical(
    nifty_future
)

bank_fut_tech = futures_technical(
    bank_future
)

# =========================================================
# TECHNICAL ANALYSIS DISPLAY
# =========================================================

st.subheader("📈 TECHNICAL ANALYSIS")

left, right = st.columns(2)


def signal_engine(
    rsi,
    price,
    vwap,
    volume
):

    if (
        pd.notna(rsi)
        and pd.notna(vwap)
        and volume > 0
    ):

        if rsi > 60 and price > vwap:

            return "🟢 BUY"

        if rsi < 40 and price < vwap:

            return "🔴 SELL"

    return "🟡 NO TRADE"


def display_technical(
    title,
    data,
    future_name
):

    st.markdown(
        f"### {title}"
    )

    st.write(
        f"Futures: **{future_name}**"
    )

    a, b = st.columns(2)

    with a:

        st.metric(
            "Price",
            f"{data['price']:,.2f}"
        )

        rsi = data["rsi"]

        if pd.notna(rsi):

            st.metric(
                "RSI (14)",
                f"{rsi:.2f}"
            )

        else:

            st.metric(
                "RSI (14)",
                "N/A"
            )

        if pd.notna(data["vwap"]):

            st.metric(
                "Futures VWAP",
                f"{data['vwap']:,.2f}"
            )

        else:

            st.metric(
                "Futures VWAP",
                "N/A"
            )

    with b:

        st.metric(
            "Volume",
            f"{data['volume']:,.0f}"
        )

        st.metric(
            "EMA 9",
            "N/A"
            if pd.isna(data["ema9"])
            else f"{data['ema9']:,.2f}"
        )

        st.metric(
            "EMA 20",
            "N/A"
            if pd.isna(data["ema20"])
            else f"{data['ema20']:,.2f}"
        )

        st.metric(
            "EMA 50",
            "N/A"
            if pd.isna(data["ema50"])
            else f"{data['ema50']:,.2f}"
        )

        st.metric(
            "EMA 200",
            "N/A"
            if pd.isna(data["ema200"])
            else f"{data['ema200']:,.2f}"
        )

    signal = signal_engine(
        data["rsi"],
        data["price"],
        data["vwap"],
        data["volume"]
    )

    st.write(
        f"**Signal Engine: {signal}**"
    )


with left:

    display_technical(
        "NIFTY",
        nifty_fut_tech,
        nifty_future["tradingsymbol"]
        if nifty_future is not None
        else "Not Found"
    )

with right:

    display_technical(
        "BANKNIFTY",
        bank_fut_tech,
        bank_future["tradingsymbol"]
        if bank_future is not None
        else "Not Found"
    )

# =========================================================
# NIFTY OPTION CHAIN
# =========================================================

st.subheader("📊 NIFTY OPTION CHAIN")

if nfo.empty:

    st.error("NFO instruments load नहीं हुए।")
    st.stop()

options = nfo[
    (nfo["name"] == "NIFTY")
    &
    (nfo["instrument_type"].isin(["CE", "PE"]))
].copy()

options["expiry"] = pd.to_datetime(
    options["expiry"]
)

today_ts = pd.Timestamp(
    dt.date.today()
)

options = options[
    options["expiry"] >= today_ts
]

if options.empty:

    st.error(
        "NIFTY option instruments नहीं मिले।"
    )
    st.stop()

expiries = sorted(
    options["expiry"].dt.date.unique()
)

expiry = st.selectbox(
    "NIFTY Expiry",
    expiries,
    index=0
)

expiry_options = options[
    options["expiry"].dt.date == expiry
].copy()

# =========================================================
# SPOT / ATM
# =========================================================

spot = nifty_price

strike_step = 50

atm = round(
    spot / strike_step
) * strike_step

st.write(
    f"**NIFTY Spot:** {spot:,.2f}"
)

st.write(
    f"**ATM Strike:** {atm:,.0f}"
)

# ATM ± 3
display_strikes = [
    atm + i * strike_step
    for i in range(-3, 4)
]

# =========================================================
# FULL OPTION QUOTES
# =========================================================

instrument_keys = []

instrument_rows = []

for _, row in expiry_options.iterrows():

    key = f"NFO:{row['tradingsymbol']}"

    instrument_keys.append(key)

    instrument_rows.append({
        "key": key,
        "symbol": row["tradingsymbol"],
        "strike": float(row["strike"]),
        "type": row["instrument_type"],
        "token": int(row["instrument_token"])
    })

all_quotes = {}

try:

    for batch in chunk_list(
        instrument_keys,
        400
    ):

        response = kite.quote(batch)

        all_quotes.update(response)

except Exception as e:

    st.error(
        f"Option quote error: {e}"
    )
    all_quotes = {}

# =========================================================
# BUILD FULL CHAIN
# =========================================================

chain_rows = []

for row in instrument_rows:

    q = all_quotes.get(
        row["key"],
        {}
    )

    ltp = safe_float(
        q.get("last_price")
    )

    volume = safe_float(
        q.get("volume")
    )

    oi = safe_float(
        q.get("oi", q.get("open_interest"))
    )

    avg_price = safe_float(
        q.get("average_price")
    )

    chain_rows.append({
        "symbol": row["symbol"],
        "strike": row["strike"],
        "type": row["type"],
        "ltp": ltp,
        "volume": volume,
        "oi": oi,
        "avg_price": avg_price
    })

chain_df = pd.DataFrame(
    chain_rows
)

# =========================================================
# SESSION OI / VOLUME SNAPSHOT
# =========================================================

snapshot_key = expiry.strftime(
    "%Y-%m-%d"
)

current_snapshot = {}

for _, row in chain_df.iterrows():

    key = (
        f"{row['symbol']}"
    )

    current_snapshot[key] = {
        "oi": row["oi"],
        "volume": row["volume"]
    }

previous_snapshot = st.session_state.option_snapshot.get(
    snapshot_key,
    {}
)

# Calculate changes
chain_df["oi_change_pct"] = np.nan
chain_df["volume_change_pct"] = np.nan

for idx, row in chain_df.iterrows():

    key = row["symbol"]

    old = previous_snapshot.get(
        key
    )

    if old:

        old_oi = safe_float(
            old.get("oi")
        )

        old_volume = safe_float(
            old.get("volume")
        )

        if old_oi > 0:

            chain_df.loc[
                idx,
                "oi_change_pct"
            ] = (
                (row["oi"] - old_oi)
                / old_oi
            ) * 100

        if old_volume > 0:

            chain_df.loc[
                idx,
                "volume_change_pct"
            ] = (
                (row["volume"] - old_volume)
                / old_volume
            ) * 100

# Save latest snapshot
st.session_state.option_snapshot[
    snapshot_key
] = current_snapshot

# =========================================================
# IV
# =========================================================

expiry_datetime = dt.datetime.combine(
    expiry,
    dt.time(15, 30)
)

seconds_left = (
    expiry_datetime - dt.datetime.now()
).total_seconds()

time_years = max(
    seconds_left / (
        365 * 24 * 60 * 60
    ),
    0.000001
)

chain_df["iv"] = np.nan

for idx, row in chain_df.iterrows():

    iv = black_scholes_iv(
        row["ltp"],
        spot,
        row["strike"],
        time_years,
        row["type"]
    )

    chain_df.loc[
        idx,
        "iv"
    ] = iv

# =========================================================
# PCR
# =========================================================

pcr = calculate_pcr(
    chain_df
)

# =========================================================
# MAX PAIN
# =========================================================

max_pain = calculate_max_pain(
    chain_df
)

m1, m2, m3 = st.columns(3)

with m1:

    st.metric(
        "PCR",
        "N/A"
        if pd.isna(pcr)
        else f"{pcr:.2f}"
    )

with m2:

    st.metric(
        "Max Pain",
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
    "IV Black-Scholes model से calculated है; "
    "यह Zerodha API का direct IV field नहीं है।"
)

st.caption(
    "OI Change % और Volume Change % "
    "dashboard session के previous snapshot से calculated हैं। "
    "कोई simulated data नहीं है।"
)

# =========================================================
# ATM ±3 DISPLAY
# =========================================================

display_df = chain_df[
    chain_df["strike"].isin(
        display_strikes
    )
].copy()

ce = display_df[
    display_df["type"] == "CE"
].set_index("strike")

pe = display_df[
    display_df["type"] == "PE"
].set_index("strike")

rows = []

for strike in display_strikes:

    ce_row = ce.loc[strike] if strike in ce.index else None
    pe_row = pe.loc[strike] if strike in pe.index else None

    rows.append({

        "Strike": strike,

        "CE LTP":
            np.nan if ce_row is None
            else ce_row["ltp"],

        "CE OI":
            np.nan if ce_row is None
            else ce_row["oi"],

        "CE OI Chg %":
            np.nan if ce_row is None
            else ce_row["oi_change_pct"],

        "CE Volume":
            np.nan if ce_row is None
            else ce_row["volume"],

        "CE Vol Chg %":
            np.nan if ce_row is None
            else ce_row["volume_change_pct"],

        "CE IV":
            np.nan if ce_row is None
            else ce_row["iv"],

        "PE LTP":
            np.nan if pe_row is None
            else pe_row["ltp"],

        "PE OI":
            np.nan if pe_row is None
            else pe_row["oi"],

        "PE OI Chg %":
            np.nan if pe_row is None
            else pe_row["oi_change_pct"],

        "PE Volume":
            np.nan if pe_row is None
            else pe_row["volume"],

        "PE Vol Chg %":
            np.nan if pe_row is None
            else pe_row["volume_change_pct"],

        "PE IV":
            np.nan if pe_row is None
            else pe_row["iv"]
    })

display_table = pd.DataFrame(
    rows
)

st.dataframe(
    display_table,
    use_container_width=True,
    hide_index=True
)

# =========================================================
# OPTION SIGNAL ENGINE
# =========================================================

st.subheader("🎯 OPTION SIGNAL ENGINE")

rsi = nifty_fut_tech["rsi"]

if pd.isna(rsi):

    st.info(
        "🟡 RSI data available नहीं है।"
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
# AUTO REFRESH
# =========================================================

st.divider()

st.subheader("🔄 Auto Refresh")

refresh_seconds = st.selectbox(
    "Refresh Interval",
    [30, 60],
    index=0
)

st.caption(
    f"Dashboard हर {refresh_seconds} सेकंड में "
    "live data refresh करेगा।"
)

time.sleep(
    refresh_seconds
)

st.rerun()
