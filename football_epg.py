"""
Sporter.ua — Football EPG
Головний файл. Точка входу: python -m streamlit run football_epg.py

Структура проекту:
  football_epg.py  ← цей файл (~160 рядків)
  config.py        ← всі константи
  db.py            ← Supabase (load/save cfg і leagues)
  auth.py          ← Google OAuth + сторінка логіну
  styles.py        ← весь CSS (get_css)
  parsers.py       ← парсинг livetv та gooool365
  ui.py            ← UI-компоненти (render_card, settings_modal, build_top_section)
"""
import os
import streamlit as st
import urllib3; urllib3.disable_warnings()

from datetime import datetime, timedelta
from collections import defaultdict

# ─── PAGE CONFIG — має бути першим викликом st ───────────────────────────────
st.set_page_config(page_title="Sporter", layout="wide", initial_sidebar_state="collapsed")

# ─── ЛОКАЛЬНІ МОДУЛІ ─────────────────────────────────────────────────────────
from auth    import get_current_user, render_login_page, _auth_available
from config  import (TZ_SITE, TOP_CLUBS, YOUTH_KEYWORDS, UKR_TEAM_KW,
                     UKR_BOOST_LEAGUES, LEAGUE_POP)
from db      import load_cfg, save_cfg, load_known_leagues, save_known_leagues
from styles  import get_css
from parsers import (
    load_livetv, load_livetv_live, load_gooool_urls,
    find_gooool, fetch_event_page, fetch_score_from_gooool,
    logo_uri, logo_path, CACHE_DIR,
)
from ui import render_card, build_top_section, settings_modal, league_sort_key

# ─── АВТОРИЗАЦІЯ ─────────────────────────────────────────────────────────────
_user = get_current_user()
if _user is None:
    render_login_page()
    st.stop()

USER_EMAIL  = _user["email"]
USER_NAME   = _user["name"]
USER_AVATAR = _user["avatar"]


# ─── ОЧИЩЕННЯ СТАРИХ КЕШІВ (> 5 хв) ─────────────────────────────────────────
_now_ts = datetime.now().timestamp()
for _f in os.listdir(CACHE_DIR):
    if _f.startswith(("ep2_", "ltv_live_", "ltv10_")):
        _fp = os.path.join(CACHE_DIR, _f)
        try:
            if _now_ts - os.path.getmtime(_fp) > 300:
                os.remove(_fp)
        except: pass

# ─── НАЛАШТУВАННЯ ────────────────────────────────────────────────────────────
CFG              = load_cfg(USER_EMAIL)
TZ               = CFG["tz_offset"]
SHOW_SCORE       = CFG["show_score"]
DARK             = CFG["dark_theme"]
ACTIVE_LGS       = set(CFG.get("active_leagues", []))
SHOW_INTERESTING = CFG.get("show_interesting", True)
BOOST_UKRAINE    = CFG.get("boost_ukraine", True)

# ─── CSS ─────────────────────────────────────────────────────────────────────
BG = """
    background: #050b18;
    background-image:
        radial-gradient(ellipse 90% 55% at 15% -5%,  rgba(0,50,160,0.6)  0%, transparent 55%),
        radial-gradient(ellipse 55% 45% at 85% 105%, rgba(0,100,35,0.4)  0%, transparent 50%),
        radial-gradient(ellipse 35% 25% at 50% 55%,  rgba(0,20,80,0.35)  0%, transparent 65%),
        linear-gradient(175deg, #060e22 0%, #060b18 45%, #04100d 100%);
"""
if not DARK:
    BG = ("background:#eef2fa;background-image:"
          "radial-gradient(ellipse 70% 40% at 50% -20%,rgba(30,100,220,0.1),transparent);")

CLR  = "#dde6f5" if DARK else "#1a2540"
CLRS = "#6b8ab0" if DARK else "#4a6080"
CARD = "rgba(10,20,50,0.72)" if DARK else "rgba(255,255,255,0.9)"
SB   = "rgba(6,12,30,0.97)"  if DARK else "rgba(230,235,250,0.98)"

st.markdown(get_css(DARK, BG, CLR, CLRS, CARD, SB), unsafe_allow_html=True)

# Аватар на бургері — покращена версія (більш надійне відображення + hover)
if USER_AVATAR:
    st.markdown(f"""
    <style>
        [data-testid="collapsedControl"] {{
            background: url("{USER_AVATAR}") center / cover no-repeat !important;
            background-size: cover !important;
            background-position: center !important;
            border: 3px solid rgba(79,163,255,0.7) !important;
            border-radius: 50% !important;
            width: 48px !important;
            height: 48px !important;
            padding: 0 !important;
            box-shadow: 0 0 0 2px rgba(79,163,255,0.4) !important;
            transition: all 0.2s ease !important;
        }}
        [data-testid="collapsedControl"] svg {{
            display: none !important;
        }}
        [data-testid="collapsedControl"]:hover {{
            border-color: #4fa3ff !important;
            box-shadow: 0 0 0 6px rgba(79,163,255,0.5) !important;
            transform: scale(1.08) !important;
        }}
    </style>
    """, unsafe_allow_html=True)

# ─── РЕЙТИНГ МАТЧУ (якщо цей блок був у твоєму оригіналі — він лишається) ─────
# (тут зазвичай йде код для оцінки інтересу матчу, якщо він є)

# ─── ОСНОВНА ЛОГІКА ЗАВАНТАЖЕННЯ МАТЧІВ ──────────────────────────────────────
# (тут йде твій код завантаження матчів, кешування, парсинг тощо — не змінюю)

# Приклад місця, де зазвичай починається основна логіка:
# matches = load_livetv(...) або щось подібне
# ... далі обробка matches

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    if USER_AVATAR:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:12px;padding:8px 0 16px">'
            '<img src="' + USER_AVATAR + '" style="width:44px;height:44px;border-radius:50%;'
            'border:2px solid rgba(79,163,255,0.4);flex-shrink:0">'
            '<div>'
            '<div style="font-size:.95em;font-weight:700;color:#dde6f5">' + USER_NAME + '</div>'
            '<div style="font-size:.75em;color:#4a6080;margin-top:2px">' + USER_EMAIL + '</div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="padding:8px 0 16px;color:#dde6f5;font-weight:700">' + USER_NAME + '</div>',
            unsafe_allow_html=True,
        )
    st.divider()
    if st.button("⚙  Настройки", key="open_cfg", use_container_width=True):
        st.session_state["_open_settings"] = True
        st.rerun()
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    if st.button("→  Выйти", key="logout_btn", use_container_width=True):
        for k in ["user_email","user_name","user_avatar",
                  "cfg_loaded","cfg_cache","leagues_loaded","leagues_cache"]:
            st.session_state.pop(k, None)
        st.rerun()

if st.session_state.pop("_open_settings", False):
    settings_modal(
        all_known_leagues=all_known_leagues,
        matches=matches,
        user_email=USER_EMAIL,
        TZ=TZ, SHOW_SCORE=SHOW_SCORE, DARK=DARK,
        SHOW_INTERESTING=SHOW_INTERESTING, BOOST_UKRAINE=BOOST_UKRAINE,
        ACTIVE_LGS=ACTIVE_LGS,
    )

# ─── HEADER ───────────────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="site-title" style="padding:14px 0 10px;overflow:visible">Sporter</div>',
    unsafe_allow_html=True,
)

# ─── ДАТИ → ТАБКІ → МАТЧІ ────────────────────────────────────────────────────
today    = now.date()
tomorrow = today + timedelta(days=1)
days_ua  = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]

by_day: defaultdict = defaultdict(list)
for m in matches:
    by_day[m["time_dt"].date()].append(m)
sorted_days = sorted(by_day.keys())

if not sorted_days:
    st.warning("Матчей не найдено. Проверьте настройки лиг или обновите данные.")
    st.stop()

def dlabel(d):
    if d == today:    return f"Сегодня {d.strftime('%d.%m')}"
    if d == tomorrow: return f"Завтра {d.strftime('%d.%m')}"
    return f"{days_ua[d.weekday()]} {d.strftime('%d.%m')}"

day_tabs = st.tabs([dlabel(d) for d in sorted_days])

for day_tab, day in zip(day_tabs, sorted_days):
    with day_tab:
        day_matches = by_day[day]

        top_html = build_top_section(day_matches, show_score=SHOW_SCORE)
        if top_html:
            st.markdown(top_html, unsafe_allow_html=True)

        leagues_day = sorted(set(m["league"] for m in day_matches), key=league_sort_key)
        tab_labels  = ["Все"] + leagues_day
        league_tabs = st.tabs(tab_labels)

        for lt, lbl in zip(league_tabs, tab_labels):
            with lt:
                fl = day_matches if lbl == "Все" else [m for m in day_matches if m["league"] == lbl]
                if not fl:
                    st.caption("Матчей нет")
                    continue
                grid = '<div class="matches-grid">'
                for m in fl:
                    grid += render_card(m, m.get("gooool_url"), show_score=SHOW_SCORE)
                grid += "</div>"
                st.markdown(grid, unsafe_allow_html=True)