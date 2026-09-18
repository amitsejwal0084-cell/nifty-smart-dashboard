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
# LOGIN
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
        st.error("❌ Zerodha Login Failed")
        st.code(str(e))
        st.stop()

# =========================================================
# HEADER
# =========================================================

st.title("📈 NIFTY Smart Technical Analysis Dashboard")

st.caption(
    "Zerodha Kite Connect • Live Market Analysis"
)

# =========================================================
# LOGIN SCREEN
# =========================================================

if not st.session_state.access_token:

    st.warning("🟡 Zerodha अभी connected नहीं है.")

    st.link_button(
        "🔐 LOGIN WITH ZERODHA",
        kite.login_url(),
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
        f"🟢 Zerodha Connected — "
        f"{profile.get('user_name', 'User')}"
    )

    st.caption(
        f"User ID: {profile.get('user_id', '')}"
    )

except Exception as e:

    st.error("🔴 Zerodha Access Token invalid/expired.")
    st.code(str(e))
    st.stop()

# =========================================================
# REFRESH
# =========================================================

c1, c2 = st.columns([1, 4])

with c1:

    if st.button(
        "🔄 Refresh",
        use_container_width=True
    ):
        st.rerun()

with c2:

    st.caption(
        "Last Update: "
        + datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    )

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)

    return 100 - (100 / (1 + rs))


def get_index_analysis(token):

    try:

        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        candles = kite.historical_data(
            token,
            start_date,
            end_date,
            "5minute"
        )

        df = pd.DataFrame(candles)

        if df.empty:
            return None

        df["date"] = pd.to_datetime(df["date"])

        df["rsi"] = rsi(df["close"])

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

        return {
            "price": float(latest["close"]),
            "rsi": float(latest["rsi"]),
            "ema9": float(latest["ema9"]),
            "ema20": float(latest["ema20"]),
            "ema50": float(latest["ema50"]),
            "ema200": float(latest["ema200"]),
            "volume": float(latest["volume"])
        }

    except Exception as e:

        return {
            "error": str(e)
        }


# =========================================================
# MARKET OVERVIEW
# =========================================================

st.divider()

st.header("📊 Market Overview")

try:

    quotes = kite.quote([
        "NSE:NIFTY 50",
        "NSE:NIFTY BANK",
        "NSE:INDIA VIX"
    ])

    nifty_live = quotes["NSE:NIFTY 50"]["last_price"]
    bank_live = quotes["NSE:NIFTY BANK"]["last_price"]
    vix_live = quotes["NSE:INDIA VIX"]["last_price"]

except Exception as e:

    st.error("❌ Live market quote error")
    st.code(str(e))
    st.stop()

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric(
        "NIFTY 50",
        f"{nifty_live:,.2f}"
    )

with m2:
    st.metric(
        "BANKNIFTY",
        f"{bank_live:,.2f}"
    )

with m3:
    st.metric(
        "INDIA VIX",
        f"{vix_live:,.2f}"
    )

with m4:
    st.metric(
        "Market Status",
        "LIVE 🟢"
    )

# =========================================================
# TECHNICAL ANALYSIS
# =========================================================

st.divider()

st.header("📈 Technical Analysis")

nifty_data = get_index_analysis(256265)
bank_data = get_index_analysis(260105)

# =========================================================
# NIFTY
# =========================================================

st.subheader("NIFTY 50")

if nifty_data and "error" not in nifty_data:

    n1, n2, n3, n4 = st.columns(4)

    with n1:
        st.metric(
            "Price",
            f"{nifty_data['price']:,.2f}"
        )

    with n2:
        st.metric(
            "RSI (14)",
            f"{nifty_data['rsi']:.2f}"
        )

    with n3:
        st.metric(
            "EMA 20",
            f"{nifty_data['ema20']:,.2f}"
        )

    with n4:
        st.metric(
            "Volume",
            f"{nifty_data['volume']:,.0f}"
        )

    st.write(
        f"EMA 9: `{nifty_data['ema9']:.2f}`"
    )

    st.write(
        f"EMA 50: `{nifty_data['ema50']:.2f}`"
    )

    st.write(
        f"EMA 200: `{nifty_data['ema200']:.2f}`"
    )

else:

    st.error(
        nifty_data.get("error", "NIFTY unavailable")
        if nifty_data
        else "NIFTY unavailable"
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
        st.metric(
            "RSI (14)",
            f"{bank_data['rsi']:.2f}"
        )

    with b3:
        st.metric(
            "EMA 20",
            f"{bank_data['ema20']:,.2f}"
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
        f"EMA 50: `{bank_data['ema50']:.2f}`"
    )

    st.write(
        f"EMA 200: `{bank_data['ema200']:.2f}`"
    )

else:

    st.error(
        bank_data.get("error", "BANKNIFTY unavailable")
        if bank_data
        else "BANKNIFTY unavailable"
    )

# =========================================================
# LOAD NFO INSTRUMENTS
# =========================================================

@st.cache_data(ttl=300)
def load_nfo_instruments():

    instruments = kite.instruments("NFO")

    return pd.DataFrame(instruments)


try:

    nfo = load_nfo_instruments()

except Exception as e:

    st.error("❌ NFO instruments load नहीं हुए.")
    st.code(str(e))
    st.stop()

# =========================================================
# NIFTY OPTION EXPIRIES
# =========================================================

st.divider()

st.header("🔗 NIFTY Option Chain")

nifty_options = nfo[
    (nfo["name"] == "NIFTY") &
    (nfo["instrument_type"].isin(["CE", "PE"]))
].copy()

if nifty_options.empty:

    st.error("❌ NIFTY option instruments नहीं मिले.")
    st.stop()

nifty_options["expiry"] = pd.to_datetime(
    nifty_options["expiry"]
)

today = pd.Timestamp.now().normalize()

future_expiries = sorted(
    nifty_options.loc[
        nifty_options["expiry"] >= today,
        "expiry"
    ].unique()
)

if not future_expiries:

    st.error("❌ कोई future NIFTY expiry नहीं मिली.")
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

expiry_df = nifty_options[
    nifty_options["expiry"] == selected_expiry
].copy()

# =========================================================
# FIND ATM
# =========================================================

try:

    spot = float(
        kite.ltp("NSE:NIFTY 50")[
            "NSE:NIFTY 50"
        ]["last_price"]
    )

except Exception:

    spot = nifty_live

strikes = sorted(
    expiry_df["strike"].unique()
)

atm_strike = min(
    strikes,
    key=lambda x: abs(x - spot)
)

# =========================================================
# ATM ±3
# =========================================================

nearest_index = strikes.index(atm_strike)

start_index = max(
    0,
    nearest_index - 3
)

end_index = min(
    len(strikes),
    nearest_index + 4
)

selected_strikes = strikes[
    start_index:end_index
]

st.write(
    f"**NIFTY Spot:** `{spot:,.2f}`"
)

st.write(
    f"**ATM Strike:** `{atm_strike:,.0f}`"
)

# =========================================================
# OPTION CONTRACTS
# =========================================================

selected_contracts = expiry_df[
    expiry_df["strike"].isin(selected_strikes)
].copy()

ce_df = selected_contracts[
    selected_contracts["instrument_type"] == "CE"
].copy()

pe_df = selected_contracts[
    selected_contracts["instrument_type"] == "PE"
].copy()

ce_df = ce_df.sort_values("strike")
pe_df = pe_df.sort_values("strike")

# =========================================================
# LIVE QUOTES
# =========================================================

all_symbols = []

for _, row in selected_contracts.iterrows():

    all_symbols.append(
        f"NFO:{row['tradingsymbol']}"
    )

quote_data = {}

try:

    if all_symbols:

        quote_data = kite.quote(all_symbols)

except Exception as e:

    st.error("❌ Option quotes प्राप्त नहीं हुए.")
    st.code(str(e))

# =========================================================
# BUILD OPTION CHAIN
# =========================================================

rows = []

for strike in selected_strikes:

    ce_row = ce_df[
        ce_df["strike"] == strike
    ]

    pe_row = pe_df[
        pe_df["strike"] == strike
    ]

    ce_symbol = None
    pe_symbol = None

    ce_ltp = np.nan
    pe_ltp = np.nan

    ce_oi = 0
    pe_oi = 0

    ce_volume = 0
    pe_volume = 0

    ce_oi_change = 0
    pe_oi_change = 0

    ce_iv = np.nan
    pe_iv = np.nan

    # ---------------- CE ----------------

    if not ce_row.empty:

        ce_symbol = (
            f"NFO:{ce_row.iloc[0]['tradingsymbol']}"
        )

        if ce_symbol in quote_data:

            q = quote_data[ce_symbol]

            ce_ltp = q.get(
                "last_price",
                np.nan
            )

            ce_oi = q.get(
                "oi",
                0
            )

            ce_volume = q.get(
                "volume",
                0
            )

            ce_iv = q.get(
                "iv",
                np.nan
            )

            ohlc = q.get("ohlc", {})

            prev_close = ohlc.get(
                "close",
                0
            )

            # Quote API does not directly give
            # previous OI change for every response.
            # We keep current OI here.
            ce_oi_change = 0

    # ---------------- PE ----------------

    if not pe_row.empty:

        pe_symbol = (
            f"NFO:{pe_row.iloc[0]['tradingsymbol']}"
        )

        if pe_symbol in quote_data:

            q = quote_data[pe_symbol]

            pe_ltp = q.get(
                "last_price",
                np.nan
            )

            pe_oi = q.get(
                "oi",
                0
            )

            pe_volume = q.get(
                "volume",
                0
            )

            pe_iv = q.get(
                "iv",
                np.nan
            )

            pe_oi_change = 0

    rows.append({

        "CE LTP": ce_ltp,
        "CE OI": ce_oi,
        "CE Volume": ce_volume,
        "Strike": strike,
        "PE Volume": pe_volume,
        "PE OI": pe_oi,
        "PE LTP": pe_ltp,
        "CE IV": ce_iv,
        "PE IV": pe_iv

    })

option_chain = pd.DataFrame(rows)

# =========================================================
# PCR
# =========================================================

total_ce_oi = option_chain["CE OI"].sum()
total_pe_oi = option_chain["PE OI"].sum()

if total_ce_oi > 0:

    pcr = (
        total_pe_oi /
        total_ce_oi
    )

else:

    pcr = np.nan

# =========================================================
# MAX PAIN
# =========================================================

def calculate_max_pain(df):

    strikes = df["Strike"].tolist()

    pain_values = {}

    for settlement in strikes:

        total_pain = 0

        for _, row in df.iterrows():

            strike = row["Strike"]

            ce_oi = row["CE OI"]
            pe_oi = row["PE OI"]

            if settlement > strike:

                total_pain += (
                    settlement - strike
                ) * ce_oi

            if settlement < strike:

                total_pain += (
                    strike - settlement
                ) * pe_oi

        pain_values[settlement] = total_pain

    if pain_values:

        return min(
            pain_values,
            key=pain_values.get
        )

    return np.nan


max_pain = calculate_max_pain(
    option_chain
)

# =========================================================
# SUMMARY
# =========================================================

o1, o2, o3 = st.columns(3)

with o1:

    st.metric(
        "ATM Strike",
        f"{atm_strike:,.0f}"
    )

with o2:

    st.metric(
        "PCR",
        f"{pcr:.2f}"
        if pd.notna(pcr)
        else "—"
    )

with o3:

    st.metric(
        "Max Pain",
        f"{max_pain:,.0f}"
        if pd.notna(max_pain)
        else "—"
    )

# =========================================================
# OPTION TABLE
# =========================================================

display_df = option_chain.copy()

display_df["CE LTP"] = display_df[
    "CE LTP"
].round(2)

display_df["PE LTP"] = display_df[
    "PE LTP"
].round(2)

display_df["CE IV"] = display_df[
    "CE IV"
].round(2)

display_df["PE IV"] = display_df[
    "PE IV"
].round(2)

display_df["CE OI"] = display_df[
    "CE OI"
].astype(int)

display_df["PE OI"] = display_df[
    "PE OI"
].astype(int)

display_df["CE Volume"] = display_df[
    "CE Volume"
].astype(int)

display_df["PE Volume"] = display_df[
    "PE Volume"
].astype(int)

display_df = display_df[
    [
        "CE LTP",
        "CE OI",
        "CE Volume",
        "CE IV",
        "Strike",
        "PE IV",
        "PE Volume",
        "PE OI",
        "PE LTP"
    ]
]

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)

# =========================================================
# SIGNAL ENGINE
# =========================================================

st.divider()

st.header("🎯 Signal Engine")

s1, s2, s3 = st.columns(3)

with s1:

    st.subheader("NIFTY")

    if nifty_data and "error" not in nifty_data:

        r = nifty_data["rsi"]

        if r > 60:

            signal = "🟢 BULLISH CONDITION"

        elif r < 40:

            signal = "🔴 BEARISH CONDITION"

        else:

            signal = "🟡 NEUTRAL"

        st.write(
            f"RSI: `{r:.2f}`"
        )

        st.info(signal)

with s2:

    st.subheader("BANKNIFTY")

    if bank_data and "error" not in bank_data:

        r = bank_data["rsi"]

        if r > 60:

            signal = "🟢 BULLISH CONDITION"

        elif r < 40:

            signal = "🔴 BEARISH CONDITION"

        else:

            signal = "🟡 NEUTRAL"

        st.write(
            f"RSI: `{r:.2f}`"
        )

        st.info(signal)

with s3:

    st.subheader("OPTION MARKET")

    st.write(
        f"PCR: `{pcr:.2f}`"
        if pd.notna(pcr)
        else "PCR: —"
    )

    st.write(
        f"Max Pain: `{max_pain:,.0f}`"
        if pd.notna(max_pain)
        else "Max Pain: —"
    )

# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "⚡ Zerodha Kite Connect • Live Market Analysis"
    )
