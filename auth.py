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
    """Сторінка входу в стилі застосунку."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Pacifico&display=swap');
    *{box-sizing:border-box}
    html,body,[class*="css"]{font-family:'Inter',sans-serif}
    #MainMenu,footer,header{visibility:hidden}
    .stApp{
        background:#050b18;
        background-image:
            radial-gradient(ellipse 90% 55% at 15% -5%,  rgba(0,50,160,0.6)  0%, transparent 55%),
            radial-gradient(ellipse 55% 45% at 85% 105%, rgba(0,100,35,0.4)  0%, transparent 50%),
            radial-gradient(ellipse 35% 25% at 50% 55%,  rgba(0,20,80,0.35)  0%, transparent 65%),
            linear-gradient(175deg, #060e22 0%, #060b18 45%, #04100d 100%);
        min-height:100vh;
    }
    .block-container{
        padding-top:0!important;
        max-width:480px!important;
        padding-left:20px!important;
        padding-right:20px!important;
    }
    @keyframes ts{0%{background-position:0%}100%{background-position:300%}}
    @keyframes fadeUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}

    .lp-wrap{
        display:flex;flex-direction:column;align-items:center;
        justify-content:center;min-height:100vh;
        padding:40px 0 60px;gap:0;
    }
    .lp-title{
        font-family:'Pacifico',cursive;
        font-size:4.2em;
        font-weight:400;
        line-height:1.25;
        padding:8px 4px 4px;
        margin:0 0 10px;
        background:linear-gradient(110deg,#a0650a 0%,#ffd234 25%,#ffe680 50%,#c8860a 75%,#ffd234 100%);
        background-size:300% auto;
        -webkit-background-clip:text;-webkit-text-fill-color:transparent;
        animation:ts 3.5s linear infinite, fadeUp .5s ease both;
    }
    .lp-sub{
        color:#6b8ab0;font-size:.95em;font-weight:500;
        margin:0 0 32px;letter-spacing:.3px;
        animation:fadeUp .6s .1s ease both;
        text-align:center;
    }
    .lp-card{
        background:rgba(10,20,50,0.75);
        border:1px solid rgba(79,163,255,0.18);
        border-radius:20px;
        padding:32px 36px 28px;
        width:100%;
        display:flex;flex-direction:column;align-items:center;gap:16px;
        box-shadow:0 8px 48px rgba(0,20,80,0.5);
        position:relative;overflow:hidden;
        animation:fadeUp .7s .15s ease both;
    }
    .lp-card::before{
        content:'';position:absolute;top:0;left:0;right:0;height:2px;
        background:linear-gradient(90deg,#1a6fff,#00c6ff,#ffd234);opacity:.85;
    }
    .lp-card-title{font-size:1.1em;font-weight:700;color:#dde6f5;margin:0;}
    .lp-card-sub{font-size:.82em;color:#4a6080;margin:0;text-align:center;line-height:1.55;}
    .lp-divider{
        width:100%;display:flex;align-items:center;gap:10px;
        color:#2a3a5a;font-size:.78em;font-weight:500;
    }
    .lp-divider::before,.lp-divider::after{content:'';flex:1;height:1px;background:rgba(79,163,255,0.12);}
    .lp-footer{
        margin-top:20px;color:#2a3a5a;font-size:.75em;text-align:center;
        line-height:1.6;animation:fadeUp .9s .3s ease both;
    }
    /* кнопка OAuth — тільки на login-сторінці */
    .stButton > button{
        width:100%!important;
        background:#ffffff!important;color:#3c4043!important;
        border:1px solid #dadce0!important;border-radius:22px!important;
        padding:10px 20px!important;
        font-family:'Inter',sans-serif!important;font-size:.93em!important;font-weight:600!important;
        height:46px!important;
        box-shadow:0 1px 3px rgba(0,0,0,0.12)!important;
        transition:box-shadow .15s,background .15s!important;
    }
    .stButton > button:hover{
        background:#f8f9fa!important;
        box-shadow:0 2px 8px rgba(0,0,0,0.16)!important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="lp-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="lp-title">Sporter</div>', unsafe_allow_html=True)
    st.markdown('<div class="lp-sub">Умное расписание футбольных матчей</div>', unsafe_allow_html=True)

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

    st.markdown('<div class="lp-footer">🔒 Мы используем только ваш email для сохранения настроек</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if result and "token" in result:
        import jwt as pyjwt
        try:
            info = pyjwt.decode(
                result["token"]["id_token"],
                options={"verify_signature": False}
            )
            st.session_state["user_email"]  = info.get("email", "")
            st.session_state["user_name"]   = info.get("name", info.get("email", ""))
            st.session_state["user_avatar"] = info.get("picture", "")
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка авторизации: {e}")


def get_current_user() -> dict | None:
    """Повертає dict з email/name/avatar або None якщо не залогінений."""
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
