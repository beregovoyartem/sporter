"""
ui.py — UI-компоненти: render_card, settings_modal, build_top_section.
Залежить від: config.py, parsers.py, db.py
"""
import os
import urllib.parse
import streamlit as st

from config import FLAG_MAP, UCL_SVG, UEL_SVG, UECL_SVG, LEAGUE_POP, TZ_SITE


def lhtml(url: str) -> str:
    """Рендерить логотип команди напряму з URL."""
    if url:
        return (f'<img src="{url}" loading="lazy" '
                f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
                f'<div class="tph" style="display:none">⚽</div>')
    return '<div class="tph">⚽</div>'


def league_badge_html(name: str) -> str:
    code = FLAG_MAP.get(name, "")
    if code == "ucl":  return f'<span class="lg-ico">{UCL_SVG}</span>'
    if code == "uel":  return f'<span class="lg-ico">{UEL_SVG}</span>'
    if code == "uecl": return f'<span class="lg-ico">{UECL_SVG}</span>'
    if code:
        return f'<img class="lg-flag" src="https://flagcdn.com/16x12/{code}.png" alt="">'
    return ''


def league_sort_key(lg: str) -> tuple:
    return (LEAGUE_POP.get(lg, 999), lg)


# ─── RENDER CARD ─────────────────────────────────────────────────────────────
def render_card(m: dict, gurl: str | None = None, feat: bool = False,
                show_score: bool = True) -> str:
    t1, t2  = m["team1"], m["team2"]
    is_live = m["status"] == "live"
    is_fin  = m["status"] == "finished"
    league  = m["league"]
    MONTHS_UA_SHORT = ["","СІЧ","ЛЮТ","БЕР","КВІ","ТРА","ЧЕР","ЛИП","СЕР","ВЕР","ЖОВ","ЛИС","ГРУ"]
    tstr    = f'{m["time_dt"].day} {MONTHS_UA_SHORT[m["time_dt"].month]} {m["time_dt"].strftime("%H:%M")}'
    score   = m.get("score") if show_score else None
    interest = m.get("interest", 0)

    if m.get("is_top"):
        stars_cls = f" stars{interest}" if interest > 0 else ""
        cls = f"mc top{stars_cls}"
    else:
        cls = "mc"
    if is_live: cls += " live"
    if feat:    cls += " feat"

    badge_html = league_badge_html(league)
    if not FLAG_MAP.get(league):
        ltv_logo = m.get("league_logo")
        if ltv_logo:
            badge_html = (f'<img src="{ltv_logo}" style="width:14px;height:14px;'
                          f'object-fit:contain;vertical-align:middle;margin-right:1px" '
                          f'onerror="this.style.display=\'none\'">')

    lg_html = (f'<div style="display:flex;align-items:center;gap:5px;flex-wrap:nowrap">'
               f'<div class="mc-league">{badge_html}{league}</div>'
               f'</div>')

    if m.get("is_top") and interest > 0:
        stars_inner = "".join('<span class="star filled">★</span>' for _ in range(interest))
        head_stars = f'<span class="star-row" style="flex-shrink:0">{stars_inner}</span>'
    else:
        head_stars = '<span class="star-row" style="flex-shrink:0"><span class="star blue">★</span></span>'

    match_date = m["time_dt"].strftime("%d.%m.%Y")
    ai_query = (
        f'{t1} vs {t2} {league} {match_date}: '
        f'составы и ключевые игроки, история личных встреч, '
        f'текущая форма команд, травмы и дисквалификации, '
        f'тактические особенности, прогноз и коэффициенты, '
        f'почему стоит посмотреть этот матч'
    )
    ai_url = 'https://www.google.com/search?q=' + urllib.parse.quote(ai_query) + '&udm=50'

    btn_ltv = f'<a class="wbtn btn-ltv" href="{m["url"]}" target="_blank">Livetv</a>'
    btn_go  = f'<a class="wbtn btn-go" href="{gurl}" target="_blank">Gooool365</a>' if gurl else ""
    sep     = '<span style="color:rgba(79,163,255,0.25);font-size:.65em">|</span>'
    links   = f'{btn_go} {sep} {btn_ltv}' if gurl else btn_ltv
    ai_prognoz = f'<a class="wbtn btn-ai-footer" href="{ai_url}" target="_blank">ПРОГНОЗ</a>'

    if is_live:
        if score and show_score:
            center = (f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px;flex-shrink:0">'
                      f'<div class="vs-b"><div class="live-badge">LIVE</div>'
                      f'<div class="sc-live">{score}</div></div>'
                      f'{ai_prognoz}</div>')
        else:
            center = (f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px;flex-shrink:0">'
                      f'<div class="vs-b"><div class="live-badge">LIVE</div></div>'
                      f'{ai_prognoz}</div>')
    elif is_fin and score and show_score:
        center = f'<div class="vs-b"><div class="sc-fin">{score}</div></div>'
    else:
        center = (f'<div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0">'
                  f'{ai_prognoz}</div>')

    footer = (f'<div class="mc-foot">'
              f'<span class="mc-date">{tstr}</span>'
              f'<div class="mc-btns">{links}</div>'
              f'</div>')

    return (f'<div class="{cls}">'
            f'<div class="mc-head" style="align-items:flex-start">{lg_html}'
            f'<div style="display:flex;align-items:center;gap:6px;flex-shrink:0">{head_stars}</div></div>'
            f'<div class="teams">'
            f'<div class="team"><div class="tlogo">{lhtml(m.get("t1_logo"))}</div>'
            f'<div class="tname">{t1}</div></div>'
            f'{center}'
            f'<div class="team"><div class="tlogo">{lhtml(m.get("t2_logo"))}</div>'
            f'<div class="tname">{t2 or "?"}</div></div>'
            f'</div>'
            f'{footer}'
            f'</div>')


# ─── BUILD TOP SECTION ────────────────────────────────────────────────────────
def build_top_section(day_matches_list: list, show_score: bool = True) -> str:
    top = sorted([m for m in day_matches_list if m.get("is_top")],
                 key=lambda x: (-x.get("interest", 0), x["time_dt"]))
    if not top:
        return ""
    hdr = ('<div class="top-hdr">'
           '<span class="top-hdr-s">✦</span>'
           '<span class="top-hdr-txt">Главные матчи дня</span>'
           '<span class="top-hdr-s">✦</span>'
           '</div>')
    rows = '<div class="top-matches-wrapper">'
    idx, n = 0, len(top)
    if idx < n:
        rows += '<div class="top-row cols1 h3">'
        rows += render_card(top[idx], top[idx].get("gooool_url"), feat=True, show_score=show_score)
        rows += '</div>'; idx += 1
    if idx < n:
        chunk = top[idx:idx+2]
        rows += f'<div class="top-row cols{len(chunk)} h2">'
        for cm in chunk:
            rows += render_card(cm, cm.get("gooool_url"), feat=True, show_score=show_score)
        rows += '</div>'; idx += len(chunk)
    if idx < n:
        chunk = top[idx:idx+3]
        rows += f'<div class="top-row cols{len(chunk)} h1">'
        for cm in chunk:
            rows += render_card(cm, cm.get("gooool_url"), feat=True, show_score=show_score)
        rows += '</div>'; idx += len(chunk)
    while idx < n:
        chunk = top[idx:idx+4]
        rows += f'<div class="top-row cols{min(len(chunk),4)} h1">'
        for cm in chunk:
            rows += render_card(cm, cm.get("gooool_url"), feat=True, show_score=show_score)
        rows += '</div>'; idx += len(chunk)
    rows += '</div>'
    return hdr + rows


# ─── SETTINGS MODAL ──────────────────────────────────────────────────────────
@st.dialog("Настройки", width="large")
def settings_modal(all_known_leagues: list, matches: list,
                   user_email: str,
                   TZ: int, SHOW_SCORE: bool, DARK: bool,
                   SHOW_INTERESTING: bool, BOOST_UKRAINE: bool,
                   ACTIVE_LGS: set):
    from db import save_cfg, save_known_leagues

    st.markdown("#### Отображение")
    TZ_OPTIONS = [
        "(UTC-5) Нью-Йорк, Торонто",
        "(UTC-4) Галифакс, Каракас",
        "(UTC-3) Буэнос-Айрес, Бразилиа",
        "(UTC-2) Середина Атлантики",
        "(UTC-1) Азорские острова",
        "(UTC+0) Лондон, Лиссабон",
        "(UTC+1) Варшава, Берлин, Рим",
        "(UTC+2) Киев, Хельсинки, Афины",
        "(UTC+3) Москва, Стамбул, Эр-Рияд",
        "(UTC+4) Баку, Дубай, Тбилиси",
        "(UTC+5) Ташкент, Карачи",
        "(UTC+6) Алматы, Дакка",
        "(UTC+7) Бангкок, Джакарта",
        "(UTC+8) Пекин, Сингапур",
        "(UTC+9) Токио, Сеул",
        "(UTC+10) Сидней, Владивосток",
        "(UTC+11) Магадан",
        "(UTC+12) Окленд, Фиджи",
    ]
    TZ_BASE = -5
    tz_idx = max(0, min(TZ - TZ_BASE, len(TZ_OPTIONS) - 1))
    new_tz_label    = st.selectbox("Мой часовой пояс", TZ_OPTIONS, index=tz_idx, key="m_tz")
    new_tz          = TZ_OPTIONS.index(new_tz_label) + TZ_BASE
    new_score       = st.checkbox("Показывать счёт", value=SHOW_SCORE, key="m_sc")
    new_interesting = st.checkbox(
        "Интересные команды — выносить матчи топ-100 клубов в «Главные матчи дня»",
        value=SHOW_INTERESTING, key="m_int",
    )
    new_boost_ukraine = st.checkbox(
        "Приоритет украинским командам в международных турнирах (ЛЧ, ЛЕ, сборные и т.д.)",
        value=BOOST_UKRAINE, key="m_ukr",
    )
    new_dark = DARK  # тема не змінюється через UI

    st.markdown("---")
    st.markdown("#### Лиги")
    st.caption("Отмеченные лиги отображаются. Если все сняты — показываются все.")

    if "lg_override" not in st.session_state:
        st.session_state.lg_override = None
    if "lg_override_gen" not in st.session_state:
        st.session_state.lg_override_gen = 0

    col_sel, col_clr, _ = st.columns([1, 1, 2])
    with col_sel:
        if st.button("Выбрать все", use_container_width=True, key="m_selall", type="primary"):
            st.session_state.lg_override = "all"
            st.session_state.lg_override_gen += 1
    with col_clr:
        if st.button("Снять все", use_container_width=True, key="m_clrall"):
            st.session_state.lg_override = "none"
            st.session_state.lg_override_gen += 1
    st.write("")

    if st.session_state.lg_override == "all":
        default_active = set(all_known_leagues)
    elif st.session_state.lg_override == "none":
        default_active = set()
    else:
        default_active = set(ACTIVE_LGS) if ACTIVE_LGS else set(all_known_leagues)

    gen = st.session_state.lg_override_gen
    new_active: set = set()
    cols_n = 4
    grid_rows = [all_known_leagues[i:i+cols_n] for i in range(0, len(all_known_leagues), cols_n)]
    for row in grid_rows:
        rcols = st.columns(cols_n)
        for col, lg in zip(rcols, row):
            with col:
                if st.checkbox(lg, value=(lg in default_active), key=f"m_lg_{lg}_{gen}"):
                    new_active.add(lg)

    st.write("")
    st.markdown("---")
    _c1, _c2, _c3 = st.columns(3)
    with _c1:
        if st.button("Сохранить", use_container_width=True, key="m_save", type="primary"):
            st.session_state.lg_override = None
            save_active = [] if new_active == set(all_known_leagues) else list(new_active)
            save_known_leagues(user_email, set(all_known_leagues))
            save_cfg(user_email, {
                "tz_offset":        new_tz,
                "show_score":       new_score,
                "dark_theme":       new_dark,
                "show_interesting": new_interesting,
                "boost_ukraine":    new_boost_ukraine,
                "active_leagues":   save_active,
            })
            st.cache_data.clear()
            st.rerun()
    with _c2:
        if st.button("Обновить данные", use_container_width=True, key="m_ref"):
            st.cache_data.clear()
            st.rerun()
    with _c3:
        if st.button("Сбросить кэш", use_container_width=True, key="m_cache"):
            st.cache_data.clear()
            st.rerun()

    st.caption(
        f"Сайт UTC+{TZ_SITE} → ваш UTC{new_tz:+d} · "
        f"{len(all_known_leagues)} лиг · {len(matches)} матчей"
    )
