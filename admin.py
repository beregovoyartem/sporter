"""
admin.py — Адмін-панель Sporter.
Доступна тільки для ADMIN_EMAIL з secrets або config.
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
    st.markdown("""
    <style>
    .adm-title { font-size:1.4em; font-weight:800; color:#dde6f5; margin-bottom:4px; }
    .adm-sub   { font-size:.82em; color:#4a6080; margin-bottom:20px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="adm-title">⚙ Адмін-панель</div>', unsafe_allow_html=True)
    st.markdown('<div class="adm-sub">Управление пользователями и настройками</div>', unsafe_allow_html=True)

    sb = _sb()

    # ── Список юзерів ────────────────────────────────────────────────────────
    st.markdown("### 👥 Пользователи")
    try:
        users_res = sb.table("user_sessions").select("email,name,created_at").order("created_at", desc=True).execute()
        users = users_res.data or []
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return

    if not users:
        st.info("Пользователей пока нет.")
        return

    # Таблиця
    col_h1, col_h2, col_h3 = st.columns([3, 3, 2])
    col_h1.markdown("**Email**")
    col_h2.markdown("**Имя**")
    col_h3.markdown("**Регистрация**")
    st.divider()

    for u in users:
        c1, c2, c3 = st.columns([3, 3, 2])
        c1.markdown(f"`{u['email']}`")
        c2.markdown(u.get("name", "—"))
        dt = u.get("created_at", "")
        if dt:
            try:
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
            except Exception:
                pass
        c3.markdown(dt or "—")

    st.markdown(f"*Всего: {len(users)} пользователей*")

    st.divider()

    # ── Массова розсилка налаштувань ─────────────────────────────────────────
    st.markdown("### 📤 Отправить настройки пользователям")

    target = st.radio(
        "Кому отправить:",
        ["Всем пользователям", "Конкретному пользователю"],
        horizontal=True,
        key="adm_target",
    )

    target_email = None
    if target == "Конкретному пользователю":
        emails = [u["email"] for u in users]
        target_email = st.selectbox("Выберите пользователя:", emails, key="adm_email_sel")

    st.markdown("#### Настройки для отправки")

    c1, c2 = st.columns(2)
    with c1:
        new_tz = st.selectbox("Часовой пояс", [
            "(UTC-5) Нью-Йорк", "(UTC-4) Каракас", "(UTC-3) Буэнос-Айрес",
            "(UTC-2) Атлантика", "(UTC-1) Азоры", "(UTC+0) Лондон",
            "(UTC+1) Берлин", "(UTC+2) Киев", "(UTC+3) Москва",
            "(UTC+4) Дубай", "(UTC+5) Карачи", "(UTC+6) Алматы",
            "(UTC+7) Бангкок", "(UTC+8) Пекин", "(UTC+9) Токио",
            "(UTC+10) Сидней", "(UTC+11) Магадан", "(UTC+12) Окленд",
        ], index=7, key="adm_tz")
        tz_val = list(range(-5, 13))[["(UTC-5) Нью-Йорк","(UTC-4) Каракас","(UTC-3) Буэнос-Айрес","(UTC-2) Атлантика","(UTC-1) Азоры","(UTC+0) Лондон","(UTC+1) Берлин","(UTC+2) Киев","(UTC+3) Москва","(UTC+4) Дубай","(UTC+5) Карачи","(UTC+6) Алматы","(UTC+7) Бангкок","(UTC+8) Пекин","(UTC+9) Токио","(UTC+10) Сидней","(UTC+11) Магадан","(UTC+12) Окленд"].index(new_tz)]
        new_score       = st.checkbox("Показывать счёт", value=True, key="adm_score")
        new_interesting = st.checkbox("Топ-клубы в главные матчи", value=True, key="adm_int")
        new_ukraine     = st.checkbox("Приоритет украинским командам", value=True, key="adm_ukr")

    with c2:
        st.markdown("**Лиги** (оставьте пустым = показывать все)")
        # Підтягуємо всі відомі ліги
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

    st.markdown("")

    if st.button("📤 Отправить настройки", type="primary", key="adm_send"):
        cfg = {
            "tz_offset":        tz_val,
            "show_score":       new_score,
            "dark_theme":       True,
            "show_interesting": new_interesting,
            "boost_ukraine":    new_ukraine,
            "active_leagues":   selected_leagues,
        }
        cfg_json = json.dumps(cfg, ensure_ascii=False)
        leagues_json = json.dumps(selected_leagues, ensure_ascii=False)

        if target == "Всем пользователям":
            targets = [u["email"] for u in users]
        else:
            targets = [target_email] if target_email else []

        ok, fail = 0, 0
        with st.spinner(f"Обновляю {len(targets)} пользователей..."):
            for email in targets:
                try:
                    sb.table("user_settings").upsert({
                        "email":    email,
                        "settings": cfg_json,
                        "updated_at": datetime.utcnow().isoformat(),
                    }).execute()
                    if selected_leagues:
                        sb.table("user_leagues").upsert({
                            "email":   email,
                            "leagues": leagues_json,
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

    # ── Скинути налаштування юзера до дефолту ────────────────────────────────
    st.markdown("### 🗑 Сбросить настройки пользователя")
    reset_email = st.selectbox("Пользователь:", [u["email"] for u in users], key="adm_reset_sel")
    if st.button("Сбросить до дефолта", key="adm_reset", type="secondary"):
        from config import DEFAULT_CFG
        try:
            sb.table("user_settings").upsert({
                "email":    reset_email,
                "settings": json.dumps(DEFAULT_CFG, ensure_ascii=False),
                "updated_at": datetime.utcnow().isoformat(),
            }).execute()
            st.success(f"✅ Настройки {reset_email} сброшены!")
        except Exception as e:
            st.error(f"Ошибка: {e}")
