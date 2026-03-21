"""
auth.py — Google OAuth через streamlit-oauth та сторінка логіну.
"""
import streamlit as st


def _auth_available() -> bool:
    try:
        return bool(st.secrets.get("GOOGLE_CLIENT_ID"))
    except Exception:
        return False


def render_login_page():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Pacifico&display=swap');
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    #MainMenu, footer, header { visibility: hidden; }

    .stApp {
        background: #050b18;
        background-image:
            radial-gradient(ellipse 90% 55% at 15% -5%,  rgba(0,50,160,0.6)  0%, transparent 55%),
            radial-gradient(ellipse 55% 45% at 85% 105%, rgba(0,100,35,0.4)  0%, transparent 50%),
            linear-gradient(175deg, #060e22 0%, #060b18 45%, #04100d 100%);
        min-height: 100vh;
    }

    section[data-testid="stMain"] > div {
        min-height: 100vh !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        align-items: center !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    .block-container {
        padding: 20px !important;
        margin: 0 auto !important;
        max-width: 440px !important;
    }

    .lp-title {
        font-family: 'Pacifico', cursive;
        font-size: 5em;
        line-height: 1.05;
        padding: 0 0 28px;
        background: linear-gradient(110deg,#a0650a 0%,#ffd234 25%,#ffe680 50%,#c8860a 75%,#ffd234 100%);
        background-size: 300% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: ts 5s linear infinite;
        text-align: center;
    }
    @keyframes ts { 0% { background-position: 0% } 100% { background-position: 300% } }

    .lp-sub {
        color: #8ab4d8;
        font-size: 1.15em;
        text-align: center;
        margin: 0 0 44px;
    }

    .lp-card {
        background: rgba(10,20,50,0.90);
        border: 1px solid rgba(79,163,255,0.28);
        border-radius: 18px;
        padding: 36px 32px 28px;
        box-shadow: 0 14px 56px rgba(0,20,80,0.5);
        position: relative;
        overflow: hidden;
        width: 100%;
    }
    .lp-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 4px;
        background: linear-gradient(90deg, #1a6fff, #00c6ff, #ffd234);
    }

    .lp-card-title {
        font-size: 1.4em;
        font-weight: 700;
        color: #dde6f5;
        text-align: center;
        margin-bottom: 14px;
    }
    .lp-card-sub {
        font-size: 1em;
        color: #8ab4d8;
        text-align: center;
        line-height: 1.6;
    }

    .lp-divider {
        display: flex;
        align-items: center;
        gap: 14px;
        color: #4a6080;
        font-size: 0.9em;
        margin: 26px 0 14px;
    }
    .lp-divider::before,
    .lp-divider::after {
        content: '';
        flex: 1;
        height: 1px;
        background: rgba(79,163,255,0.20);
    }

    div.stButton > button {
        margin-top: 22px !important;
        height: 54px !important;
        font-size: 1.1em !important;
        font-weight: 600 !important;
        background: #ffffff !important;
        color: #1f1f1f !important;
        border: 1px solid #dadce0 !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.12) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 14px !important;
        width: 100% !important;
        transition: all 0.2s !important;
    }
    div.stButton > button:hover {
        background: #f8f9fa !important;
        box-shadow: 0 4px 14px rgba(0,0,0,0.18) !important;
    }

    div.stButton > button::before {
        content: "";
        width: 22px;
        height: 22px;
        background: url('https://developers.google.com/identity/images/g-logo.png') no-repeat center;
        background-size: contain;
    }

    .lp-footer {
        color: #6b8ab0;
        font-size: 0.85em;
        text-align: center;
        margin-top: 30px;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="lp-title">Sporter</div>', unsafe_allow_html=True)
    st.markdown('<div class="lp-sub">Умное расписание футбольных матчей</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="lp-card">
        <div class="lp-card-title">Добро пожаловать</div>
        <div class="lp-card-sub">
            Войдите, чтобы сохранять настройки<br>
            и выбранные лиги между сессиями
        </div>
        <div class="lp-divider">войти через</div>
    </div>
    """, unsafe_allow_html=True)

    from streamlit_oauth import OAuth2Component
    oauth2 = OAuth2Component(
        client_id=st.secrets["GOOGLE_CLIENT_ID"],
        client_secret=st.secrets["GOOGLE_CLIENT_SECRET"],
        authorize_endpoint="https://accounts.google.com/o/oauth2/auth",
        token_endpoint="https://oauth2.googleapis.com/token",
    )

    oauth2.authorize_button(
        name="Войти через Google",
        redirect_uri=st.secrets["REDIRECT_URI"],
        scope="openid email profile",
        key="google_login",
        use_container_width=True,
    )

    st.markdown('<div class="lp-footer">🔒 Мы используем только ваш email для сохранения настроек</div>', unsafe_allow_html=True)


def get_current_user() -> dict | None:
    if not _auth_available():
        return {"email": "local", "name": "Local", "avatar": ""}
    email = st.session_state.get("user_email")
    if not email:
        return None
    return {
        "email":  email,
        "name":   st.session_state.get("user_name", email),
        "avatar": st.session_state.get("user_avatar", ""),
    }