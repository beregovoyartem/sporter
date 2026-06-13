"""
admin.py — Адмін-панель Sporter.
"""
import json
import streamlit as st
from datetime import datetime


def _sb():
    from supabase import create_client
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def is_admin(email: str) -> bool:
    try:
        admin = st.secrets.get("ADMIN_EMAIL", "")
        return bool(email and admin and email.lower() == admin.lower())
    except Exception:
        return False


def render_admin_page(user_email: str):
    st.markdown("## ⚙ Админ")
    st.caption("Управление пользователями и настройками")
    st.divider()

    sb = _sb()

    # ── Завантажуємо юзерів і ліги один раз в session_state ─────────────────
    if "adm_users" not in st.session_state:
        try:
            res = sb.table("user_sessions").select("email,name,created_at").order("created_at", desc=True).execute()
            st.session_state.adm_users = res.data or []
        except Exception as e:
            st.error(f"Ошибка загрузки: {e}")
            return

    if "adm_all_leagues" not in st.session_state:
        try:
            from db import load_global_leagues
            st.session_state.adm_all_leagues = sorted(load_global_leagues())
        except Exception:
            # Fallback — збираємо з user_leagues
            try:
                res2 = sb.table("user_leagues").select("leagues").execute()
                known = set()
                for row in (res2.data or []):
                    try: known.update(json.loads(row["leagues"]))
                    except: pass
                st.session_state.adm_all_leagues = sorted(known)
            except Exception:
                st.session_state.adm_all_leagues = []

    users      = st.session_state.adm_users
    all_leagues = st.session_state.adm_all_leagues

    if not users:
        st.info("Пользователей пока нет.")
        return

    # ── Налаштування ─────────────────────────────────────────────────────────
    st.markdown("### Настройки")

    TZ_OPTIONS = [
        "(UTC-5) Нью-Йорк, Торонто",
        "(UTC-4) Галифакс, Каракас",
        "(UTC-3) Буэнос-Айрес, Бразилиа",
        "(UTC-2) Середина Атлантики",
        "(UTC-1) Азорские острова",
        "(UTC+0) Лондон, Лиссабон",
        "(UTC+1) Варшава, Берлин, Рим",
        "(UTC+2) Хельсинки, Афины",
        "(UTC+3) Киев, Стамбул, Эр-Рияд",
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
    
    new_tz_auto     = st.checkbox("Автоопределение таймзоны", value=True, key="adm_tzauto")
    tz_label        = st.selectbox("Часовой пояс", TZ_OPTIONS, index=8, key="adm_tz", disabled=new_tz_auto)
    tz_val          = TZ_OPTIONS.index(tz_label) + TZ_BASE
    
    new_score       = st.checkbox("Показывать счёт", value=True, key="adm_score")
    new_interesting = st.checkbox(
        "Интересные команды — выносить матчи топ-100 клубов в «Главные матчи дня»",
        value=True, key="adm_int",
    )
    new_ukraine     = st.checkbox(
        "Приоритет украинским командам в международных турнирах (ЛЧ, ЛЕ, сборные и т.д.)",
        value=True, key="adm_ukr",
    )

    # ── Ліги чекбоксами (як в settings_modal) ────────────────────────────────
    st.markdown("**Лиги** (пусто = показывать все)")

    # Ініціалізуємо стан ліг
    if "adm_lg_override" not in st.session_state:
        st.session_state.adm_lg_override = None
    if "adm_lg_gen" not in st.session_state:
        st.session_state.adm_lg_gen = 0

    col_sel, col_clr, _ = st.columns([1, 1, 4])
    with col_sel:
        if st.button("Выбрать все лиги", key="adm_lg_all"):
            st.session_state.adm_lg_override = "all"
            st.session_state.adm_lg_gen += 1
    with col_clr:
        if st.button("Снять все лиги", key="adm_lg_none"):
            st.session_state.adm_lg_override = "none"
            st.session_state.adm_lg_gen += 1

    if st.session_state.adm_lg_override == "all":
        default_lg = set(all_leagues)
    elif st.session_state.adm_lg_override == "none":
        default_lg = set()
    else:
        default_lg = set()  # за замовчуванням — всі (порожньо = без фільтру)

    gen = st.session_state.adm_lg_gen
    selected_leagues = set()
    cols_n = 4
    rows = [all_leagues[i:i+cols_n] for i in range(0, len(all_leagues), cols_n)]
    for row in rows:
        rcols = st.columns(cols_n)
        for col, lg in zip(rcols, row):
            with col:
                if st.checkbox(lg, value=(lg in default_lg), key=f"adm_lg_{lg}_{gen}"):
                    selected_leagues.add(lg)

    st.divider()

    # ── Кому відправити — чекбокси без rerun ─────────────────────────────────
    st.markdown("### Кому отправить")

    # Ініціалізуємо стан юзерів
    if "adm_usr_override" not in st.session_state:
        st.session_state.adm_usr_override = None
    if "adm_usr_gen" not in st.session_state:
        st.session_state.adm_usr_gen = 0

    cu1, cu2, _ = st.columns([1, 1, 4])
    with cu1:
        if st.button("Выбрать всех", key="adm_selall"):
            st.session_state.adm_usr_override = "all"
            st.session_state.adm_usr_gen += 1
    with cu2:
        if st.button("Снять всех", key="adm_selnone"):
            st.session_state.adm_usr_override = "none"
            st.session_state.adm_usr_gen += 1

    if st.session_state.adm_usr_override == "all":
        default_usr = True
    elif st.session_state.adm_usr_override == "none":
        default_usr = False
    else:
        default_usr = False

    ugen = st.session_state.adm_usr_gen
    selected_users = []
    
    unique_users = {}
    for u in users:
        if u['email'] not in unique_users:
            unique_users[u['email']] = u
            
    for i, u in enumerate(unique_users.values()):
        key = f"adm_u_{u['email']}_{i}_{ugen}"
        checked = st.checkbox(
            f"**{u.get('name', u['email'])}** — `{u['email']}`",
            value=default_usr,
            key=key,
        )
        if checked:
            selected_users.append(u["email"])

    st.divider()

    # ── Кнопка відправки ─────────────────────────────────────────────────────
    n = len(selected_users)
    if st.button(
        f"📤 Отправить {n} пользователям" if n > 0 else "📤 Отправить",
        type="primary",
        key="adm_send",
        disabled=(n == 0),
    ):
        cfg = {
            "tz_offset":        tz_val,
            "tz_auto":          new_tz_auto,
            "show_score":       new_score,
            "dark_theme":       True,
            "show_interesting": new_interesting,
            "boost_ukraine":    new_ukraine,
            "active_leagues":   list(selected_leagues),
        }
        cfg_json     = json.dumps(cfg, ensure_ascii=False)
        leagues_json = json.dumps(sorted(selected_leagues), ensure_ascii=False)

        ok = fail = 0
        with st.spinner(f"Обновляю {n} пользователей..."):
            for email in selected_users:
                try:
                    sb.table("user_settings").upsert({
                        "email":      email,
                        "settings":   cfg_json,
                        "updated_at": datetime.utcnow().isoformat(),
                    }).execute()
                    if selected_leagues:
                        sb.table("user_leagues").upsert({
                            "email":      email,
                            "leagues":    leagues_json,
                            "updated_at": datetime.utcnow().isoformat(),
                        }).execute()
                    ok += 1
                except Exception as e:
                    fail += 1
                    st.warning(f"{email}: {e}")

        if ok:   st.success(f"✅ Обновлено {ok} пользователей!")
        if fail: st.error(f"❌ Ошибок: {fail}")

    st.divider()

    # ── Скинути до дефолту ────────────────────────────────────────────────────
    st.markdown("### Сбросить настройки пользователя")
    reset_email = st.selectbox("Пользователь:", [u["email"] for u in users], key="adm_reset_sel")
    if st.button("Сбросить до дефолта", key="adm_reset"):
        from config import DEFAULT_CFG
        try:
            sb.table("user_settings").upsert({
                "email":      reset_email,
                "settings":   json.dumps(DEFAULT_CFG, ensure_ascii=False),
                "updated_at": datetime.utcnow().isoformat(),
            }).execute()
            st.success(f"✅ Настройки {reset_email} сброшены!")
        except Exception as e:
            st.error(f"Ошибка: {e}")

    st.divider()
    if st.button("← Назад на главную", key="adm_back"):
        for k in ["adm_users", "adm_all_leagues", "adm_lg_override",
                  "adm_lg_gen", "adm_usr_override", "adm_usr_gen"]:
            st.session_state.pop(k, None)
        st.query_params.clear()
        st.rerun()
