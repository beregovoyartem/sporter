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
    st.markdown("## ⚙ Адмін-панель")
    st.caption("Управление пользователями и настройками")
    st.divider()

    sb = _sb()

    # ── Завантажуємо юзерів ──────────────────────────────────────────────────
    try:
        res = sb.table("user_sessions").select("email,name,created_at").order("created_at", desc=True).execute()
        users = res.data or []
    except Exception as e:
        st.error(f"Ошибка загрузки пользователей: {e}")
        return

    if not users:
        st.info("Пользователей пока нет.")
        return

    # ── Налаштування для відправки ───────────────────────────────────────────
    st.markdown("### Настройки")

    TZ_OPTIONS = [
        ("(UTC-5) Нью-Йорк", -5), ("(UTC-4) Каракас", -4), ("(UTC-3) Буэнос-Айрес", -3),
        ("(UTC-2) Атлантика", -2), ("(UTC-1) Азоры", -1), ("(UTC+0) Лондон", 0),
        ("(UTC+1) Берлин", 1), ("(UTC+2) Киев", 2), ("(UTC+3) Москва", 3),
        ("(UTC+4) Дубай", 4), ("(UTC+5) Карачи", 5), ("(UTC+6) Алматы", 6),
        ("(UTC+7) Бангкок", 7), ("(UTC+8) Пекин", 8), ("(UTC+9) Токио", 9),
        ("(UTC+10) Сидней", 10), ("(UTC+11) Магадан", 11), ("(UTC+12) Окленд", 12),
    ]
    tz_labels = [t[0] for t in TZ_OPTIONS]
    tz_values = [t[1] for t in TZ_OPTIONS]

    tz_label = st.selectbox("Часовой пояс", tz_labels, index=7, key="adm_tz")
    tz_val   = tz_values[tz_labels.index(tz_label)]

    new_score       = st.checkbox("Показывать счёт", value=True, key="adm_score")
    new_interesting = st.checkbox("Топ-клубы в главные матчи", value=True, key="adm_int")
    new_ukraine     = st.checkbox("Приоритет украинским командам", value=True, key="adm_ukr")

    st.markdown("**Лиги** (пусто = показывать все)")
    try:
        all_lg_res = sb.table("user_leagues").select("leagues").execute()
        all_known = set()
        for row in (all_lg_res.data or []):
            try:
                all_known.update(json.loads(row["leagues"]))
            except Exception:
                pass
        all_known = sorted(all_known)
    except Exception:
        all_known = []

    selected_leagues = st.multiselect(
        "Выбрать лиги:",
        options=all_known,
        key="adm_leagues",
        placeholder="Все лиги (без фильтра)",
    )

    st.divider()

    # ── Список юзерів з чекбоксами ───────────────────────────────────────────
    st.markdown("### Кому отправить")

    # Кнопки вибрати всіх / зняти всіх
    col_all, col_none, _ = st.columns([1, 1, 4])
    with col_all:
        if st.button("Выбрать всех", key="adm_selall"):
            for u in users:
                st.session_state[f"adm_u_{u['email']}"] = True
    with col_none:
        if st.button("Снять всех", key="adm_selnone"):
            for u in users:
                st.session_state[f"adm_u_{u['email']}"] = False

    selected_users = []
    for u in users:
        key = f"adm_u_{u['email']}"
        checked = st.checkbox(
            f"**{u.get('name', u['email'])}** — `{u['email']}`",
            value=st.session_state.get(key, False),
            key=key,
        )
        if checked:
            selected_users.append(u["email"])

    st.divider()

    # ── Кнопка відправки ─────────────────────────────────────────────────────
    n = len(selected_users)
    btn_label = f"📤 Отправить {n} пользователям" if n > 0 else "📤 Отправить (выберите пользователей)"

    if st.button(btn_label, type="primary", key="adm_send", disabled=(n == 0)):
        cfg = {
            "tz_offset":        tz_val,
            "show_score":       new_score,
            "dark_theme":       True,
            "show_interesting": new_interesting,
            "boost_ukraine":    new_ukraine,
            "active_leagues":   selected_leagues,
        }
        cfg_json    = json.dumps(cfg, ensure_ascii=False)
        leagues_json = json.dumps(selected_leagues, ensure_ascii=False)

        ok, fail = 0, 0
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

        if ok:
            st.success(f"✅ Обновлено {ok} пользователей!")
        if fail:
            st.error(f"❌ Ошибок: {fail}")

    st.divider()

    # ── Скинути юзера до дефолту ─────────────────────────────────────────────
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
    if st.button("← Назад", key="adm_back"):
        st.rerun()
