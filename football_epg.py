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

# ─── ЗАВАНТАЖЕННЯ ДАНИХ ──────────────────────────────────────────────────────
pb = st.progress(0, text="Загрузка livetv.sx...")
ltv             = load_livetv()
pb.progress(40, text="Live матчи...")
live_data       = load_livetv_live()
live_ids_set    = set(live_data.get("ids", []))
live_scores_map = live_data.get("scores", {})
pb.progress(55, text="gooool365...")
glist = load_gooool_urls()
pb.progress(85, text="Обработка...")

now = datetime.utcnow() + timedelta(hours=TZ)

# ─── ОНОВЛЕННЯ LIVE-СТАТУСІВ ─────────────────────────────────────────────────
seen_ids: set = set()
combined: list = []
for m in ltv["top"] + ltv["all"]:
    if m["event_id"] in seen_ids: continue
    seen_ids.add(m["event_id"])
    eid = m["event_id"]
    if eid in live_ids_set:
        try:
            match_dt = datetime.fromisoformat(m["time"])
            minutes_since = (datetime.now() - match_dt).total_seconds() / 60
            if -2 <= minutes_since <= 140:
                m = dict(m)
                m["status"] = "live"
                if eid in live_scores_map:
                    m["score"] = live_scores_map[eid]
        except: pass
    combined.append(m)

# ─── ЛІГИ (накопичені + поточні) ─────────────────────────────────────────────
all_known_leagues_current = set(m["league"] for m in combined)
_saved_leagues            = load_known_leagues(USER_EMAIL)
all_known_leagues_merged  = all_known_leagues_current | _saved_leagues
if all_known_leagues_current - _saved_leagues:
    save_known_leagues(USER_EMAIL, all_known_leagues_merged)
all_known_leagues = sorted(all_known_leagues_merged, key=league_sort_key)

# ─── ФІЛЬТРАЦІЯ МАТЧІВ ───────────────────────────────────────────────────────
def league_allowed(lg: str) -> bool:
    return True if not ACTIVE_LGS else lg in ACTIVE_LGS

matches: list = []
for gm in combined:
    try:
        dt = datetime.fromisoformat(gm["time"])
        dt = dt + timedelta(hours=TZ - TZ_SITE)
    except: continue
    gurl         = find_gooool(gm["team1"], gm["team2"], glist)
    i_score      = match_interest_score(gm["team1"], gm["team2"], gm.get("league","")) if SHOW_INTERESTING else 0
    is_top_final = gm.get("is_top") or (i_score > 0)
    if not league_allowed(gm["league"]): continue
    user_selected = bool(ACTIVE_LGS) and gm["league"] in ACTIVE_LGS
    if not gurl and not gm.get("always_show") and not is_top_final and not user_selected: continue
    matches.append({**gm, "time_dt": dt, "gooool_url": gurl,
                    "is_top": is_top_final, "interest": i_score})

matches.sort(key=lambda x: x["time_dt"])
for m in matches:
    if m["status"] == "upcoming":
        m["score"] = None

pb.progress(100, text="Готово!")
pb.empty()

# ─── РАХУНОК + ЛОГОТИПИ ──────────────────────────────────────────────────────
need_page = [m for m in matches if
    (SHOW_SCORE and m["status"] in ("live","finished") and not m.get("score")) or
    (not m.get("t1_logo") or not m.get("t2_logo"))]

if need_page:
    ev_bar = st.progress(0, text=f"Детали: 0/{min(len(need_page),50)}")
    for i, m in enumerate(need_page[:50]):
        data = fetch_event_page(m["event_id"], m["url"], m["status"])
        if SHOW_SCORE and m["status"] in ("live","finished") and not m.get("score") and data.get("score"):
            m["score"] = data["score"]
        if SHOW_SCORE and m["status"] == "live" and not m.get("score") and m.get("gooool_url"):
            gscore = fetch_score_from_gooool(m["gooool_url"])
            if gscore: m["score"] = gscore
        if not m.get("t1_logo") and data.get("t1"): m["t1_logo"] = data["t1"]
        if not m.get("t2_logo") and data.get("t2"): m["t2_logo"] = data["t2"]
        ev_bar.progress((i+1)/min(len(need_page),50), text=f"Детали: {i+1}/{min(len(need_page),50)}")
    ev_bar.empty()

# ─── КЕШ ЛОГОТИПІВ НА ДИСК ───────────────────────────────────────────────────
to_cache = [m for m in matches if
    (m.get("t1_logo") and not os.path.exists(logo_path(m["t1_logo"]))) or
    (m.get("t2_logo") and not os.path.exists(logo_path(m["t2_logo"])))]
if to_cache:
    lc_bar = st.progress(0, text=f"Кэш лого: 0/{len(to_cache)}")
    for i, m in enumerate(to_cache):
        if m.get("t1_logo"): logo_uri(m["t1_logo"])
        if m.get("t2_logo"): logo_uri(m["t2_logo"])
        lc_bar.progress((i+1)/len(to_cache), text=f"Кэш лого: {i+1}/{len(to_cache)}")
    lc_bar.empty()

# ─── TOPBAR ──────────────────────────────────────────────────────────────────
_avatar_img = (
    f'<img src="{USER_AVATAR}" style="width:38px;height:38px;border-radius:50%;'
    f'object-fit:cover;border:2px solid rgba(79,163,255,0.5)">'
    if USER_AVATAR else
    f'<div style="width:38px;height:38px;border-radius:50%;background:rgba(79,163,255,0.12);'
    f'border:2px solid rgba(79,163,255,0.3);display:flex;align-items:center;'
    f'justify-content:center;font-size:1.1em">👤</div>'
)

_col_user, _col_cfg, _col_out = st.columns([1, 0.07, 0.07])

with _col_user:
    st.markdown(
        f'<div class="sp-topbar-user">'
        f'  {_avatar_img}'
        f'  <div class="sp-topbar-info">'
        f'    <span class="sp-topbar-name">{USER_NAME}</span>'
        f'    <span class="sp-topbar-email">{USER_EMAIL}</span>'
        f'  </div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with _col_cfg:
    if st.button("⚙", key="open_cfg", help="Настройки", use_container_width=True):
        st.session_state["_open_settings"] = True
        st.rerun()

with _col_out:
    if st.button("⏻", key="logout_btn", help="Выйти", use_container_width=True):
        for k in ["user_email","user_name","user_avatar",
                  "cfg_loaded","cfg_cache","leagues_loaded","leagues_cache"]:
            st.session_state.pop(k, None)
        st.rerun()

st.markdown('<div class="sp-topbar-divider"></div>', unsafe_allow_html=True)

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
