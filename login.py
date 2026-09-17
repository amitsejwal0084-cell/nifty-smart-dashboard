import streamlit as st
from kiteconnect import KiteConnect


st.set_page_config(
    page_title="Kite Login",
    page_icon="🔐"
)

st.title("🔐 Zerodha Kite Connect Login")

st.write(
    "नीचे दिए button से Zerodha login शुरू करें।"
)


# ---------------------------------------------------------
# API KEY
# ---------------------------------------------------------

try:
    api_key = st.secrets["KITE_API_KEY"]

except Exception:

    st.error(
        "KITE_API_KEY अभी Streamlit Secrets में configured नहीं है."
    )

    st.stop()


# ---------------------------------------------------------
# KITE OBJECT
# ---------------------------------------------------------

kite = KiteConnect(
    api_key=api_key
)


# ---------------------------------------------------------
# LOGIN URL
# ---------------------------------------------------------

login_url = kite.login_url()


st.link_button(
    "🔐 LOGIN WITH ZERODHA",
    login_url
)


st.divider()

st.info(
    "Zerodha login के बाद आपके Kite App में configured "
    "Redirect URL पर वापस भेजा जाएगा."
)
