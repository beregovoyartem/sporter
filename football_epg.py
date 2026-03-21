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
from db      import load_cfg, save_cfg, load_known_leagues, save_known_leagues, save_global_leagues
from styles  import get_css
from ui      import render_card, build_top_section, settings_modal, league_sort_key
from admin   import render_admin_page, is_admin

# ─── АВТОРИЗАЦІЯ ─────────────────────────────────────────────────────────────
_user = get_current_user()
if _user is None:
    render_login_page()
    st.stop()

USER_EMAIL  = _user["email"]
USER_NAME   = _user["name"]
USER_AVATAR = _user["avatar"]


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



# ─── РЕЙТИНГ МАТЧУ ───────────────────────────────────────────────────────────
def club_rating(name: str) -> int:
    nl = name.lower()
    return max((r for club, r in TOP_CLUBS.items() if club in nl), default=0)

def match_interest_score(team1: str, team2: str, league: str = "") -> int:
    combined = (team1 + " " + team2).lower()
    if any(kw in combined for kw in YOUTH_KEYWORDS):
        return 0
    base = max(club_rating(team1), club_rating(team2))
    if BOOST_UKRAINE and league in UKR_BOOST_LEAGUES:
        if any(kw in combined for kw in UKR_TEAM_KW):
            base = max(base, 3)
    return base

# ─── ЗАВАНТАЖЕННЯ ДАНИХ З SUPABASE ───────────────────────────────────────────
pb = st.progress(0, text="Загрузка матчей...")

@st.cache_data(ttl=120)
def _load_matches_from_db() -> list:
    """Читає матчі з Supabase таблиці matches."""
    try:
        from supabase import create_client
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        # Завантажуємо матчі за останні 2 дні і наступні 7 днів
        from datetime import timezone
        now_utc = datetime.now(timezone.utc)
        date_from = (now_utc - timedelta(days=2)).isoformat()
        date_to   = (now_utc + timedelta(days=7)).isoformat()
        res = sb.table("matches") \
            .select("*") \
            .gte("time", date_from) \
            .lte("time", date_to) \
            .order("time") \
            .execute()
        return res.data or []
    except Exception as e:
        print(f"DB load error: {e}", flush=True)
        return []

raw_matches = _load_matches_from_db()
pb.progress(70, text="Обработка...")

now = datetime.utcnow() + timedelta(hours=TZ)

# ─── ЛІГИ ────────────────────────────────────────────────────────────────────
all_known_leagues_current = set(m["league"] for m in raw_matches if m.get("league"))
_saved_leagues            = load_known_leagues(USER_EMAIL)
all_known_leagues_merged  = all_known_leagues_current | _saved_leagues
if all_known_leagues_current - _saved_leagues:
    save_known_leagues(USER_EMAIL, all_known_leagues_merged)
all_known_leagues = sorted(all_known_leagues_merged, key=league_sort_key)

# ─── ФІЛЬТРАЦІЯ МАТЧІВ ───────────────────────────────────────────────────────
def league_allowed(lg: str) -> bool:
    return True if not ACTIVE_LGS else lg in ACTIVE_LGS

matches: list = []
for gm in raw_matches:
    try:
        # Час з БД вже в UTC — конвертуємо в часовий пояс юзера
        time_str = gm["time"]
        if time_str.endswith("+00:00") or time_str.endswith("Z"):
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            dt = dt.replace(tzinfo=None) + timedelta(hours=TZ)
        else:
            dt = datetime.fromisoformat(time_str) + timedelta(hours=TZ - TZ_SITE)
    except:
        continue

    league = gm.get("league", "")
    if not league_allowed(league):
        continue

    i_score      = match_interest_score(gm.get("team1",""), gm.get("team2",""), league) if SHOW_INTERESTING else 0
    is_top_final = gm.get("is_top") or (i_score > 0)
    user_selected = bool(ACTIVE_LGS) and league in ACTIVE_LGS
    gurl = gm.get("gooool_url")

    if not gurl and not gm.get("always_show") and not is_top_final and not user_selected:
        continue

    matches.append({
        **gm,
        "time_dt":    dt,
        "gooool_url": gurl,
        "is_top":     is_top_final,
        "interest":   i_score,
        "score":      gm.get("score") if gm.get("status") != "upcoming" else None,
    })

matches.sort(key=lambda x: x["time_dt"])

pb.progress(100, text="Готово!")
pb.empty()

# ─── HEADER ──────────────────────────────────────────────────────────────────
# Спочатку кнопки (зверху), потім аватар + лого

# Адмін-сторінка — використовуємо query_params щоб пережити rerun
if st.query_params.get("page") == "admin" and is_admin(USER_EMAIL):
    render_admin_page(USER_EMAIL)
    st.stop()

if is_admin(USER_EMAIL):
    _bcol1, _bcol2, _bcol3 = st.columns([1, 1, 1])
else:
    _bcol1, _bcol2 = st.columns([1, 1])
    _bcol3 = None

with _bcol1:
    if st.button("Настройки", key="open_cfg", use_container_width=True):
        st.session_state["_open_settings"] = True
        st.rerun()
with _bcol2:
    if st.button("Выйти", key="logout_btn", use_container_width=True):
        from auth import logout
        logout()
        st.rerun()
if _bcol3:
    with _bcol3:
        if st.button("👑 Админ", key="open_admin", use_container_width=True):
            st.query_params["page"] = "admin"
            st.rerun()

_avatar_src = USER_AVATAR or ""
# Google фото: замінюємо розмір на більший щоб не пікселилось і не обрізалось
if _avatar_src and "googleusercontent.com" in _avatar_src:
    import re as _re
    _avatar_src = _re.sub(r'=s\d+-c', '=s256-c', _avatar_src)
    if "=s" not in _avatar_src:
        _avatar_src = _avatar_src + "=s256-c"
_avatar_block = (
    f'<div class="sp-hdr-avatar-wrap">'
    f'  <img src="{_avatar_src}" class="sp-hdr-avatar">'
    f'</div>'
    if _avatar_src else
    '<div class="sp-hdr-avatar-wrap sp-hdr-avatar-ph">👤</div>'
)
st.markdown(
    f'<div class="sp-hdr">'
    f'  {_avatar_block}'
    f'  <div class="site-title">Sporter</div>'
    f'</div>',
    unsafe_allow_html=True,
)

if st.session_state.pop("_open_settings", False):
    settings_modal(
        all_known_leagues=all_known_leagues,
        matches=matches,
        user_email=USER_EMAIL,
        TZ=TZ, SHOW_SCORE=SHOW_SCORE, DARK=DARK,
        SHOW_INTERESTING=SHOW_INTERESTING, BOOST_UKRAINE=BOOST_UKRAINE,
        ACTIVE_LGS=ACTIVE_LGS,
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
