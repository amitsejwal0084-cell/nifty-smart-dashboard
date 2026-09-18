import streamlit as st
from kiteconnect import KiteConnect
from urllib.parse import urlparse


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
# READ STREAMLIT SECRETS
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
# CREATE KITE OBJECT
# =========================================================

kite = KiteConnect(
    api_key=API_KEY
)


# =========================================================
# CHECK REQUEST TOKEN
# =========================================================

request_token = st.query_params.get("request_token")


# =========================================================
# GENERATE ACCESS TOKEN
# =========================================================

if request_token and st.session_state.access_token is None:

    try:

        session_data = kite.generate_session(
            request_token,
            api_secret=API_SECRET
        )

        access_token = session_data["access_token"]

        st.session_state.access_token = access_token

        st.session_state.kite_user = session_data.get(
            "user_name",
            session_data.get("user_id", "Zerodha User")
        )

        # Request token को URL से हटाएँ
        st.query_params.clear()

        st.success(
            "🟢 Zerodha Login Successful!"
        )

        st.rerun()

    except Exception as e:

        st.error(
            "❌ Zerodha Login / Token Exchange Failed"
        )

        st.code(str(e))

        st.info(
            "Request token नया होना चाहिए और कुछ मिनट में expire हो जाता है."
        )


# =========================================================
# SET ACCESS TOKEN
# =========================================================

if st.session_state.access_token:

    kite.set_access_token(
        st.session_state.access_token
    )


# =========================================================
# HEADER
# =========================================================

st.title(
    "📈 NIFTY Smart Technical Analysis Dashboard"
)

st.caption(
    "Zerodha Kite Connect • Live Market Analysis"
)


# =========================================================
# CONNECTION
# =========================================================

if st.session_state.access_token:

    try:

        profile = kite.profile()

        st.success(
            f"🟢 Zerodha Connected — "
            f"{profile.get('user_name', 'User')}"
        )

        st.write(
            f"User ID: `{profile.get('user_id', '')}`"
        )

    except Exception as e:

        st.error(
            "🔴 Access Token invalid या expired है."
        )

        st.code(str(e))

else:

    st.warning(
        "🟡 Zerodha अभी connected नहीं है."
    )

    st.write(
        "Live market data शुरू करने के लिए पहले Zerodha Login करें."
    )

    login_url = kite.login_url()

    st.link_button(
        "🔐 LOGIN WITH ZERODHA",
        login_url,
        use_container_width=True
    )


# =========================================================
# MARKET OVERVIEW
# =========================================================

st.divider()

st.header(
    "📊 Market Overview"
)


col1, col2, col3, col4 = st.columns(4)


with col1:

    st.metric(
        "NIFTY 50",
        "—"
    )


with col2:

    st.metric(
        "BANKNIFTY",
        "—"
    )


with col3:

    st.metric(
        "INDIA VIX",
        "—"
    )


with col4:

    st.metric(
        "Market Status",
        "WAITING"
    )


# =========================================================
# TECHNICAL ANALYSIS
# =========================================================

st.divider()

st.header(
    "📈 Technical Analysis"
)


technical_rows = [

    ["LTP", "—", "Waiting"],
    ["RSI (14)", "—", "Waiting"],
    ["VWAP", "—", "Waiting"],
    ["EMA 9", "—", "Waiting"],
    ["EMA 20", "—", "Waiting"],
    ["EMA 50", "—", "Waiting"],
    ["EMA 200", "—", "Waiting"],
    ["MACD", "—", "Waiting"],
    ["ATR", "—", "Waiting"],
    ["Volume", "—", "Waiting"],
    ["Volume Change", "—", "Waiting"],

]


st.dataframe(

    technical_rows,

    column_config={
        0: "Parameter",
        1: "Value",
        2: "Status"
    },

    use_container_width=True,
    hide_index=True
)


# =========================================================
# SIGNAL ENGINE
# =========================================================

st.divider()

st.header(
    "🎯 Signal Engine"
)


s1, s2, s3 = st.columns(3)


with s1:

    st.subheader(
        "NIFTY"
    )

    st.warning(
        "🟡 NO TRADE"
    )

    st.write(
        "Confidence: — / 100"
    )


with s2:

    st.subheader(
        "BANKNIFTY"
    )

    st.warning(
        "🟡 NO TRADE"
    )

    st.write(
        "Confidence: — / 100"
    )


with s3:

    st.subheader(
        "Overall Market"
    )

    st.warning(
        "🟡 WAITING"
    )


# =========================================================
# OPTION ANALYSIS
# =========================================================

st.divider()

st.header(
    "🔗 Option Market Analysis"
)


option_rows = [

    ["ATM Strike", "—"],
    ["Call OI", "—"],
    ["Put OI", "—"],
    ["Call OI Change", "—"],
    ["Put OI Change", "—"],
    ["PCR", "—"],
    ["IV", "—"],
    ["Max Pain", "—"],

]


st.dataframe(

    option_rows,

    column_config={
        0: "Parameter",
        1: "Value"
    },

    use_container_width=True,
    hide_index=True
)


# =========================================================
# TRADE PLAN
# =========================================================

st.divider()

st.header(
    "💰 Trade Plan"
)


t1, t2, t3, t4 = st.columns(4)


with t1:

    st.metric(
        "Entry",
        "—"
    )


with t2:

    st.metric(
        "Stop Loss",
        "—"
    )


with t3:

    st.metric(
        "Target 1",
        "—"
    )


with t4:

    st.metric(
        "Target 2",
        "—"
    )


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "⚡ Live tick-by-tick WebSocket engine अगला चरण है."
)
