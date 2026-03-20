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
    .block-container{padding-top:0!important;max-width:1500px!important;
        display:flex;align-items:center;justify-content:center;min-height:100vh;}
    @keyframes ts{0%{background-position:0%}100%{background-position:300%}}
    @keyframes fadeUp{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:translateY(0)}}
    @keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
    .login-page{display:flex;flex-direction:column;align-items:center;
        justify-content:center;min-height:100vh;gap:0;padding:40px 20px;}
    .login-ball{font-size:3.2em;animation:spin 8s linear infinite;margin-bottom:8px;
        filter:drop-shadow(0 0 24px rgba(255,210,52,0.4));}
    .login-title{font-family:'Pacifico',cursive;font-size:clamp(3em,8vw,5.5em);
        font-weight:400;line-height:1.1;margin:0 0 16px;
        background:linear-gradient(110deg,#a0650a 0%,#ffd234 25%,#ffe680 50%,#c8860a 75%,#ffd234 100%);
        background-size:300% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;
        animation:ts 3.5s linear infinite, fadeUp .6s ease both;}
    .login-sub{color:#6b8ab0;font-size:1.05em;font-weight:500;margin:0 0 48px;
        letter-spacing:.3px;animation:fadeUp .7s .1s ease both;}
    .login-card{background:rgba(10,20,50,0.72);border:1px solid rgba(79,163,255,0.16);
        border-radius:24px;padding:40px 44px 36px;width:100%;max-width:420px;
        display:flex;flex-direction:column;align-items:center;gap:20px;
        box-shadow:0 8px 60px rgba(0,20,80,0.5);position:relative;overflow:hidden;
        animation:fadeUp .8s .2s ease both;}
    .login-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;
        background:linear-gradient(90deg,#1a6fff,#00c6ff,#ffd234);opacity:.8;}
    .login-card-title{font-size:1.15em;font-weight:700;color:#dde6f5;letter-spacing:.2px;margin:0;}
    .login-card-sub{font-size:.85em;color:#4a6080;margin:0;text-align:center;line-height:1.5;}
    .login-divider{width:100%;display:flex;align-items:center;gap:12px;
        color:#2a3a5a;font-size:.8em;font-weight:500;}
    .login-divider::before,.login-divider::after{content:'';flex:1;height:1px;background:rgba(79,163,255,0.1);}
    .stButton > button{width:100%!important;background:#fff!important;color:#3c4043!important;
        border:1px solid #dadce0!important;border-radius:24px!important;padding:12px 24px!important;
        font-family:'Inter',sans-serif!important;font-size:.95em!important;font-weight:600!important;
        display:flex!important;align-items:center!important;justify-content:center!important;
        gap:12px!important;cursor:pointer!important;transition:background .15s,box-shadow .15s!important;
        box-shadow:0 1px 3px rgba(0,0,0,0.12)!important;letter-spacing:.2px!important;height:48px!important;}
    .stButton > button:hover{background:#f8f9fa!important;box-shadow:0 2px 8px rgba(0,0,0,0.18)!important;
        border-color:#c6c9cc!important;}
    .stButton > button:active{background:#f1f3f4!important;box-shadow:none!important;}
    .login-footer{margin-top:32px;color:#2a3a5a;font-size:.78em;text-align:center;
        line-height:1.6;animation:fadeUp 1s .4s ease both;}
    </style>
    <div class="login-page">
        <div class="login-ball">⚽</div>
        <div class="login-title">Sporter</div>
        <div class="login-sub">Футбольный EPG — прямые трансляции и расписание матчей</div>
    </div>
    """, unsafe_allow_html=True)

    _, card_col, _ = st.columns([1, 1.2, 1])
    with card_col:
        st.markdown("""
        <div class="login-card">
            <div class="login-card-title">Добро пожаловать</div>
            <div class="login-card-sub">Войдите чтобы сохранять настройки<br>и выбранные лиги между сессиями</div>
            <div class="login-divider">войти через</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="display:flex;align-items:center;justify-content:center;margin-bottom:-8px">
        <svg width="20" height="20" viewBox="0 0 48 48" style="position:absolute;z-index:10;margin-left:-120px;pointer-events:none">
          <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
          <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
          <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
          <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
          <path fill="none" d="M0 0h48v48H0z"/>
        </svg>
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
            name="  Войти через Google",
            redirect_uri=st.secrets["REDIRECT_URI"],
            scope="openid email profile",
            key="google_login",
            use_container_width=True,
        )

        st.markdown("""
        <div class="login-footer">
            🔒 Мы используем только ваш email<br>
            для сохранения настроек. Никаких лишних данных.
        </div>
        """, unsafe_allow_html=True)

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
