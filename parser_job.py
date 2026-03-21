"""
parser_job.py — GitHub Action скрипт.
Парсить livetv.sx і зберігає результати в Supabase.

Режими запуску:
  python parser_job.py matches   — повний парсинг матчів (кожні 2 год)
  python parser_job.py live      — оновлення live рахунків (кожні 10 хв)
  python parser_job.py leagues   — оновлення ліг і логотипів (раз на добу)
"""
import os
import sys
import json
import time
import hashlib
import requests
import urllib3
from datetime import datetime, timedelta

urllib3.disable_warnings()

# ─── SUPABASE ────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }

def sb_upsert(table: str, rows: list):
    if not rows:
        return
    # Батчами по 500
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/{table}",
            headers={**sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=batch,
            timeout=30,
        )
        if r.status_code not in (200, 201):
            print(f"  Supabase upsert error {r.status_code}: {r.text[:200]}", flush=True)

def sb_select(table: str, params: str = ""):
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}?{params}",
        headers=sb_headers(),
        timeout=15,
    )
    if r.status_code == 200:
        return r.json()
    return []

def sb_set_meta(key: str, value: str):
    sb_upsert("parse_meta", [{"key": key, "value": value, "updated_at": datetime.utcnow().isoformat()}])

def sb_get_meta(key: str) -> str:
    rows = sb_select("parse_meta", f"key=eq.{key}&select=value")
    return rows[0]["value"] if rows else ""


# ─── ІМПОРТ ПАРСЕРІВ (з поточної директорії) ─────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Мокаємо streamlit перед імпортом парсерів
class _MockST:
    """Мок streamlit для запуску парсерів без Streamlit."""

    @staticmethod
    def cache_data(fn=None, ttl=None, show_spinner=None):
        """Декоратор @st.cache_data — просто повертає функцію без кешу."""
        def decorator(f):
            return f
        if fn is not None:
            return fn  # @st.cache_data без дужок
        return decorator  # @st.cache_data(ttl=...)

    class secrets:
        @staticmethod
        def get(key, default=None):
            return os.environ.get(key, default)

sys.modules["streamlit"] = _MockST()

from parsers import load_livetv, load_livetv_live, load_gooool_urls, find_gooool


# ─── MODE: MATCHES ────────────────────────────────────────────────────────────
def run_matches():
    print(f"[{datetime.utcnow().isoformat()}] Парсинг матчів...", flush=True)

    ltv = load_livetv()
    all_matches = ltv.get("top", []) + ltv.get("all", [])
    print(f"  Знайдено {len(all_matches)} матчів", flush=True)

    # Завантажуємо gooool urls
    glist = []
    try:
        glist = load_gooool_urls()
        print(f"  Gooool: {len(glist)} посилань", flush=True)
    except Exception as e:
        print(f"  Gooool помилка: {e}", flush=True)

    # Формуємо рядки для БД
    now = datetime.utcnow().isoformat()
    rows = []
    seen = set()
    for m in all_matches:
        eid = m.get("event_id", "")
        if not eid or eid in seen:
            continue
        seen.add(eid)

        gurl = None
        try:
            gurl = find_gooool(m.get("team1",""), m.get("team2",""), glist)
        except Exception:
            pass

        rows.append({
            "event_id":   eid,
            "time":       m.get("time", now),
            "team1":      m.get("team1", ""),
            "team2":      m.get("team2", ""),
            "league":     m.get("league", ""),
            "league_raw": m.get("league_raw", ""),
            "league_logo":m.get("league_logo"),
            "status":     m.get("status", "upcoming"),
            "score":      m.get("score"),
            "url":        m.get("url", ""),
            "t1_logo":    m.get("t1_logo"),
            "t2_logo":    m.get("t2_logo"),
            "is_top":     bool(m.get("is_top", False)),
            "always_show":bool(m.get("always_show", False)),
            "gooool_url": gurl,
            "updated_at": now,
        })

    print(f"  Зберігаємо {len(rows)} матчів в Supabase...", flush=True)
    sb_upsert("matches", rows)

    # Оновлюємо ліги
    leagues = sorted(set(m.get("league","") for m in all_matches if m.get("league")))
    _update_global_leagues(leagues)

    sb_set_meta("matches_updated", now)
    print(f"  Готово! Матчів: {len(rows)}, Ліг: {len(leagues)}", flush=True)


# ─── MODE: LIVE ───────────────────────────────────────────────────────────────
def run_live():
    print(f"[{datetime.utcnow().isoformat()}] Оновлення live рахунків...", flush=True)

    live_data = load_livetv_live()
    live_ids   = set(live_data.get("ids", []))
    live_scores = live_data.get("scores", {})

    if not live_ids:
        print("  Активних матчів немає, пропускаємо", flush=True)
        sb_set_meta("live_updated", datetime.utcnow().isoformat())
        return

    print(f"  Live матчів: {len(live_ids)}", flush=True)
    now = datetime.utcnow().isoformat()

    # Оновлюємо статус і рахунок для live матчів
    rows = []
    for eid in live_ids:
        row = {
            "event_id":   eid,
            "status":     "live",
            "updated_at": now,
        }
        if eid in live_scores:
            row["score"] = live_scores[eid]
        rows.append(row)

    # Також переводимо завершені матчі в finished
    # (матчі які були live > 2 год тому)
    cutoff = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    old_live = sb_select("matches", f"status=eq.live&time=lt.{cutoff}&select=event_id")
    for m in old_live:
        eid = m["event_id"]
        if eid not in live_ids:
            rows.append({"event_id": eid, "status": "finished", "updated_at": now})

    if rows:
        sb_upsert("matches", rows)
        print(f"  Оновлено {len(rows)} матчів", flush=True)

    sb_set_meta("live_updated", now)
    print("  Готово!", flush=True)


# ─── MODE: LEAGUES ────────────────────────────────────────────────────────────
def run_leagues():
    print(f"[{datetime.utcnow().isoformat()}] Оновлення ліг...", flush=True)

    # Всі ліги з таблиці матчів
    rows = sb_select("matches", "select=league")
    leagues = sorted(set(r["league"] for r in rows if r.get("league")))
    _update_global_leagues(leagues)

    sb_set_meta("leagues_updated", datetime.utcnow().isoformat())
    print(f"  Ліг: {len(leagues)}", flush=True)


def _update_global_leagues(new_leagues: list):
    """Додає нові ліги до global_leagues (ніколи не видаляє)."""
    try:
        existing = sb_select("global_leagues", "id=eq.1&select=leagues")
        current = set(json.loads(existing[0]["leagues"])) if existing else set()
        merged  = current | set(new_leagues)
        if merged == current:
            return
        requests.post(
            f"{SUPABASE_URL}/rest/v1/global_leagues",
            headers={**sb_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json={"id": 1, "leagues": json.dumps(sorted(merged), ensure_ascii=False),
                  "updated_at": datetime.utcnow().isoformat()},
            timeout=15,
        )
        print(f"  Ліг збережено: {len(merged)} (+{len(merged-current)} нових)", flush=True)
    except Exception as e:
        print(f"  Leagues update error: {e}", flush=True)


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "matches"
    t0 = time.time()

    if mode == "matches":
        run_matches()
    elif mode == "live":
        run_live()
    elif mode == "leagues":
        run_leagues()
    else:
        print(f"Невідомий режим: {mode}")
        sys.exit(1)

    print(f"Час виконання: {time.time()-t0:.1f}с", flush=True)
