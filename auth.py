"""
auth.py — Google OAuth через streamlit-oauth та сторінка логіну.
Сесія зберігається в cookies через extra_streamlit_components.
"""
import streamlit as st


def _auth_available() -> bool:
    try:
        return bool(st.secrets.get("GOOGLE_CLIENT_ID"))
    except Exception:
        return False


def _get_cookie_manager():
    try:
        import extra_streamlit_components as stx
        return stx.CookieManager(key="sp_cm")
    except Exception:
        return None


def _save_session_cookies(email: str, name: str, avatar: str):
    cm = _get_cookie_manager()
    if cm is None:
        return
    try:
        from datetime import datetime, timedelta
        expires = datetime.now() + timedelta(days=30)
        cm.set("sp_email",  email,  expires_at=expires)
        cm.set("sp_name",   name,   expires_at=expires)
        cm.set("sp_avatar", avatar, expires_at=expires)
    except Exception:
        pass


def _clear_session_cookies():
    cm = _get_cookie_manager()
    if cm is None:
        return
    try:
        cm.delete("sp_email")
        cm.delete("sp_name")
        cm.delete("sp_avatar")
    except Exception:
        pass


def _restore_from_cookies():
    if st.session_state.get("user_email"):
        return
    cm = _get_cookie_manager()
    if cm is None:
        return
    try:
        cookies = cm.get_all()
        email = cookies.get("sp_email", "")
        if email:
            st.session_state["user_email"]  = email
            st.session_state["user_name"]   = cookies.get("sp_name", email)
            st.session_state["user_avatar"] = cookies.get("sp_avatar", "")
    except Exception:
        pass


def render_login_page():
    _restore_from_cookies()
    if st.session_state.get("user_email"):
        st.rerun()
        return

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
    .block-container {
        max-width: 440px !important;
        padding: 0 20px !important;
        padding-bottom: 0 !important;
        margin: 0 auto !important;
    }
    section[data-testid="stMain"] > div {
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding-bottom: 0 !important;
    }
    section[data-testid="stMain"] { padding-bottom: 0 !important; }
    div[data-testid="stBottom"] { display: none !important; }
    .block-container > div > div > div > div { margin: 0 !important; padding: 0 !important; }
    .block-container iframe { display: block !important; margin: 0 !important; }

    @keyframes ts { 0% { background-position: 0% } 100% { background-position: 300% } }

    .lp-title {
        font-family: 'Pacifico', cursive;
        font-size: 4em; line-height: 1.2;
        padding: 4px 4px 16px; margin: 0 0 4px;
        background: linear-gradient(110deg,#a0650a 0%,#ffd234 25%,#ffe680 50%,#c8860a 75%,#ffd234 100%);
        background-size: 300% auto;
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        animation: ts 3.5s linear infinite;
        text-align: center; display: block; overflow: visible;
    }
    .lp-sub {
        color: #6b8ab0; font-size: .93em; font-weight: 500;
        text-align: center; margin: 0 0 20px; display: block;
    }
    .lp-card {
        background: rgba(10,20,50,0.78);
        border: 1px solid rgba(79,163,255,0.18);
        border-radius: 18px;
        padding: 24px 28px 20px;
        position: relative; overflow: hidden;
    }
    .lp-card::before {
        content: ''; position: absolute;
        top: 0; left: 0; right: 0; height: 2px;
        background: linear-gradient(90deg, #1a6fff, #00c6ff, #ffd234);
    }
    .lp-card-title {
        font-size: 1.05em; font-weight: 700; color: #dde6f5;
        text-align: center; margin-bottom: 8px;
    }
    .lp-card-sub { font-size: .82em; color: #4a6080; text-align: center; line-height: 1.55; }
    .lp-divider {
        display: flex; align-items: center; gap: 10px;
        color: #2a3a5a; font-size: .75em; font-weight: 500; margin-top: 16px;
    }
    .lp-divider::before, .lp-divider::after {
        content: ''; flex: 1; height: 1px; background: rgba(79,163,255,0.12);
    }
    .stButton > button {
        width: 100% !important; background: #fff !important; color: #3c4043 !important;
        border: 1px solid rgba(79,163,255,0.2) !important;
        border-radius: 14px !important; height: 48px !important;
        font-family: 'Inter', sans-serif !important; font-size: .93em !important;
        font-weight: 600 !important; box-shadow: 0 4px 20px rgba(0,20,80,0.3) !important;
        margin: 10px 0 0 !important; padding: 0 !important;
    }
    .stButton > button:hover { background: #f4f7ff !important; }
    .lp-footer { color: #2a3a5a; font-size: .73em; text-align: center; margin-top: 14px; display: block; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<span class="lp-title">Sporter</span>', unsafe_allow_html=True)
    st.markdown('<span class="lp-sub">Умное расписание футбольных матчей</span>', unsafe_allow_html=True)
    st.markdown("""
    <div class="lp-card">
        <div class="lp-card-title">Добро пожаловать</div>
        <div class="lp-card-sub">Войдите чтобы сохранять настройки<br>и выбранные лиги между сессиями</div>
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
    result = oauth2.authorize_button(
        name="Войти через Google",
        redirect_uri=st.secrets["REDIRECT_URI"],
        scope="openid email profile",
        key="google_login",
        use_container_width=True,
    )
    st.markdown('<span class="lp-footer">🔒 Мы используем только ваш email для сохранения настроек</span>', unsafe_allow_html=True)

    if result and "token" in result:
        import jwt as pyjwt
        try:
            info = pyjwt.decode(result["token"]["id_token"], options={"verify_signature": False})
            email  = info.get("email", "")
            name   = info.get("name", info.get("email", ""))
            avatar = info.get("picture", "")
            st.session_state["user_email"]  = email
            st.session_state["user_name"]   = name
            st.session_state["user_avatar"] = avatar
            _save_session_cookies(email, name, avatar)
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка авторизации: {e}")


def get_current_user() -> dict | None:
    if not _auth_available():
        return {"email": "local", "name": "Local", "avatar": ""}
    _restore_from_cookies()
    email = st.session_state.get("user_email")
    if not email:
        return None
    return {
        "email":  email,
        "name":   st.session_state.get("user_name", email),
        "avatar": st.session_state.get("user_avatar", ""),
    }


def logout():
    """Повний вихід — чистить session_state і cookies."""
    _clear_session_cookies()
    for k in ["user_email", "user_name", "user_avatar",
              "cfg_loaded", "cfg_cache", "leagues_loaded", "leagues_cache"]:
        st.session_state.pop(k, None)
