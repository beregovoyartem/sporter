"""
parser_job.py — GitHub Action скрипт.
Парсить livetv.sx і зберігає результати в Supabase.

Режими запуску:
  python parser_job.py matches   — повний парсинг матчів (кожні 2 год)
  python parser_job.py live      — оновлення live рахунків (кожні 10 хв)
  python parser_job.py leagues   — оновлення ліг і логотипів (раз на добу)
"""
import os
import re
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


# ─── SUPABASE STORAGE — ЛОГОТИПИ ─────────────────────────────────────────────
# Логотипи скачуються з livetv.sx один раз і зберігаються назавжди.
# При повторних парсингах — просто перевіряємо наявність і повертаємо готовий URL.

_logo_cache: dict = {}  # локальний кеш в межах одного запуску

def upload_logo_to_storage(url: str) -> str | None:
    """
    Скачує логотип і завантажує в Supabase Storage (бакет 'logos').
    Повертає публічний URL або None при помилці.
    Якщо файл вже є в Storage — одразу повертає URL без повторного скачування.
    """
    if not url:
        return None

    # Локальний кеш — не робимо зайвих запитів в межах одного запуску
    if url in _logo_cache:
        return _logo_cache[url]

    ext_m = re.search(r"\.(gif|png|jpg|jpeg|svg|webp)(\?.*)?$", url, re.I)
    ext   = ext_m.group(1).lower() if ext_m else "gif"
    fname = hashlib.md5(url.encode()).hexdigest()[:16] + "." + ext
    public_url = f"{SUPABASE_URL}/storage/v1/object/public/logos/{fname}"

    # Перевіряємо — вже є в Storage?
    check = requests.get(public_url, timeout=5)
    if check.status_code == 200:
        _logo_cache[url] = public_url
        return public_url

    # Скачуємо з livetv.sx
    try:
        r = requests.get(
            url, timeout=8,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            verify=False,
        )
        r.raise_for_status()
        if len(r.content) < 300:
            _logo_cache[url] = None
            return None
    except Exception as e:
        print(f"  Logo download error {url}: {e}", flush=True)
        _logo_cache[url] = None
        return None

    # Визначаємо MIME
    mime = {
        "gif":  "image/gif",
        "png":  "image/png",
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "svg":  "image/svg+xml",
        "webp": "image/webp",
    }.get(ext, "image/gif")

    # Завантажуємо в Storage
    upload = requests.post(
        f"{SUPABASE_URL}/storage/v1/object/logos/{fname}",
        headers={
            "apikey":        SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type":  mime,
            "x-upsert":      "false",  # не перезаписувати якщо вже є
        },
        data=r.content,
        timeout=15,
    )

    if upload.status_code in (200, 201):
        _logo_cache[url] = public_url
        return public_url

    # Якщо помилка "already exists" (409) — файл вже є, просто повертаємо URL
    if upload.status_code == 409:
        _logo_cache[url] = public_url
        return public_url

    print(f"  Storage upload error {upload.status_code}: {upload.text[:150]}", flush=True)
    # Fallback — повертаємо оригінальний URL, щоб хоч щось показалось
    _logo_cache[url] = url
    return url


# ─── ІМПОРТ ПАРСЕРІВ (з поточної директорії) ─────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Мокаємо streamlit перед імпортом парсерів
class _MockST:
    """Мок streamlit для запуску парсерів без Streamlit."""

    @staticmethod
    def cache_data(fn=None, ttl=None, show_spinner=None):
        def decorator(f):
            return f
        if fn is not None:
            return fn
        return decorator

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

    # Збираємо всі унікальні URL логотипів заздалегідь
    logo_urls = set()
    for m in all_matches:
        if m.get("t1_logo"): logo_urls.add(m["t1_logo"])
        if m.get("t2_logo"): logo_urls.add(m["t2_logo"])

    print(f"  Завантажуємо {len(logo_urls)} логотипів в Storage...", flush=True)
    uploaded = failed = skipped = 0
    for logo_url in logo_urls:
        result = upload_logo_to_storage(logo_url)
        if result is None:
            failed += 1
        elif result == logo_url:
            skipped += 1  # fallback — залишили оригінальний URL
        else:
            uploaded += 1
    print(f"  Логотипи: {uploaded} завантажено, {skipped} fallback, {failed} помилок", flush=True)

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

        # Логотипи: беремо з кешу (вже завантажені вище) або fallback на оригінальний URL
        t1_logo_raw = m.get("t1_logo")
        t2_logo_raw = m.get("t2_logo")
        t1_logo = _logo_cache.get(t1_logo_raw, t1_logo_raw) if t1_logo_raw else None
        t2_logo = _logo_cache.get(t2_logo_raw, t2_logo_raw) if t2_logo_raw else None

        rows.append({
            "event_id":    eid,
            "time":        m.get("time", now),
            "team1":       m.get("team1", ""),
            "team2":       m.get("team2", ""),
            "league":      m.get("league", ""),
            "league_raw":  m.get("league_raw", ""),
            "league_logo": m.get("league_logo"),
            "status":      m.get("status", "upcoming"),
            "score":       m.get("score"),
            "url":         m.get("url", ""),
            "t1_logo":     t1_logo,
            "t2_logo":     t2_logo,
            "is_top":      bool(m.get("is_top", False)),
            "always_show": bool(m.get("always_show", False)),
            "gooool_url":  gurl,
            "updated_at":  now,
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

    # Переводимо завершені матчі в finished (були live > 2 год тому)
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
