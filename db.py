"""
db.py — Supabase-інтеграція та функції load/save для налаштувань і ліг.
Залежить від: config.py
"""
import json
import streamlit as st
from datetime import datetime

from config import DEFAULT_CFG


# ─── SUPABASE HELPERS ────────────────────────────────────────────────────────
def _supabase_available() -> bool:
    try:
        return bool(st.secrets.get("SUPABASE_URL") and st.secrets.get("SUPABASE_KEY"))
    except Exception:
        return False


def _sb_load_cfg(email: str) -> dict | None:
    if not _supabase_available():
        return None
    try:
        from supabase import create_client
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        res = sb.table("user_settings").select("settings").eq("email", email).execute()
        if res.data:
            return json.loads(res.data[0]["settings"])
    except Exception as e:
        print(f"Supabase load: {e}", flush=True)
    return None


def _sb_save_cfg(email: str, cfg: dict):
    if not _supabase_available():
        return
    try:
        from supabase import create_client
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        sb.table("user_settings").upsert({
            "email":    email,
            "settings": json.dumps(cfg, ensure_ascii=False),
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception as e:
        print(f"Supabase save: {e}", flush=True)


def _sb_load_leagues(email: str) -> set:
    if not _supabase_available():
        return set()
    try:
        from supabase import create_client
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        res = sb.table("user_leagues").select("leagues").eq("email", email).execute()
        if res.data:
            return set(json.loads(res.data[0]["leagues"]))
    except Exception as e:
        print(f"Supabase load leagues: {e}", flush=True)
    return set()


def _sb_save_leagues(email: str, leagues: set):
    if not _supabase_available():
        return
    try:
        from supabase import create_client
        sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        sb.table("user_leagues").upsert({
            "email":   email,
            "leagues": json.dumps(sorted(leagues), ensure_ascii=False),
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()
    except Exception as e:
        print(f"Supabase save leagues: {e}", flush=True)


# ─── PUBLIC API ───────────────────────────────────────────────────────────────
def load_cfg(user_email: str) -> dict:
    """Завантажує налаштування: Supabase → session_state → дефолт."""
    if "cfg_loaded" in st.session_state:
        return dict(st.session_state.cfg_cache)
    from_sb = _sb_load_cfg(user_email)
    cfg = dict(DEFAULT_CFG)
    if from_sb:
        cfg.update(from_sb)
    st.session_state.cfg_cache  = dict(cfg)
    st.session_state.cfg_loaded = True
    return cfg


def save_cfg(user_email: str, d: dict):
    """Зберігає налаштування в Supabase + оновлює session_state."""
    st.session_state.cfg_cache  = dict(d)
    st.session_state.cfg_loaded = True
    _sb_save_cfg(user_email, d)


def load_known_leagues(user_email: str) -> set:
    """Завантажує накопичений список ліг юзера."""
    if "leagues_loaded" in st.session_state:
        return set(st.session_state.leagues_cache)
    leagues = _sb_load_leagues(user_email)
    st.session_state.leagues_cache  = sorted(leagues)
    st.session_state.leagues_loaded = True
    return leagues


def save_known_leagues(user_email: str, leagues: set):
    """Зберігає список ліг: тільки додає, ніколи не видаляє."""
    existing = load_known_leagues(user_email)
    merged   = existing | leagues
    st.session_state.leagues_cache  = sorted(merged)
    st.session_state.leagues_loaded = True
    _sb_save_leagues(user_email, merged)
