"""
parsers.py — парсинг livetv.sx та gooool365.org.
Залежить від: config.py
"""
import re
import os
import json
import base64
import hashlib
import requests
import streamlit as st
from datetime import datetime
from bs4 import BeautifulSoup

from config import (
    HDR, TZ_SITE, MONTHS_RU, LEAGUE_MAP, NON_FOOTBALL,
    PRIORITY_LEAGUES, UKR_KW, FLAG_MAP,
)

# ─── ШЛЯХИ (передаються ззовні, але fallback тут) ────────────────────────────
import os as _os
_BASE      = _os.path.dirname(_os.path.abspath(__file__))
_CACHE_DIR = _os.path.join(_BASE, "epg_cache")
_LOGOS_DIR = _os.path.join(_CACHE_DIR, "logos")
for _d in (_CACHE_DIR, _LOGOS_DIR):
    _os.makedirs(_d, exist_ok=True)

CACHE_DIR = _CACHE_DIR
LOGOS_DIR = _LOGOS_DIR


# ─── JSON КЕШ ────────────────────────────────────────────────────────────────
def _cp(k):
    return os.path.join(CACHE_DIR, hashlib.md5(k.encode()).hexdigest()[:12] + ".json")

def cache_get(k, ttl=300):
    p = _cp(k)
    if os.path.exists(p) and datetime.now().timestamp() - os.path.getmtime(p) < ttl:
        try: return json.load(open(p, encoding="utf-8"))
        except: pass
    return None

def cache_set(k, d):
    try: json.dump(d, open(_cp(k), "w", encoding="utf-8"), ensure_ascii=False)
    except: pass


# ─── ФАЙЛОВИЙ КЕШ ЛОГОТИПІВ ──────────────────────────────────────────────────
def logo_path(url):
    ext = re.search(r"\.(gif|png|jpg|jpeg|svg|webp)(\?.*)?$", url, re.I)
    ext = ext.group(1).lower() if ext else "gif"
    return os.path.join(LOGOS_DIR, hashlib.md5(url.encode()).hexdigest()[:16] + "." + ext)

def logo_uri(url, ttl_days=7):
    if not url: return None
    p = logo_path(url)
    if not (os.path.exists(p) and datetime.now().timestamp() - os.path.getmtime(p) < ttl_days * 86400):
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
            r.raise_for_status()
            if len(r.content) < 300: return None
            open(p, "wb").write(r.content)
        except: return None
    try:
        data = open(p, "rb").read()
        ext = p.rsplit(".", 1)[-1]
        mt = {"gif":"image/gif","png":"image/png","jpg":"image/jpeg",
              "jpeg":"image/jpeg","svg":"image/svg+xml","webp":"image/webp"}.get(ext,"image/gif")
        return f"data:{mt};base64," + base64.b64encode(data).decode()
    except: return None


# ─── ХЕЛПЕРИ ─────────────────────────────────────────────────────────────────
def fix_url(src: str) -> str | None:
    if not src: return None
    src = src.strip()
    # Відносний шлях типу "./files/1110.gif" — не можемо використати
    if src.startswith("./") or src.startswith("../"):
        return None
    if src.startswith("//"): return "https:" + src
    if src.startswith("/"): return "https://livetv.sx" + src
    if src.startswith("http"): return src
    return None

def map_league(raw_bracket: str) -> str:
    lo = raw_bracket.lower().strip()
    for kws, name in LEAGUE_MAP:
        if any(k in lo for k in kws):
            return name
    clean = re.sub(r'^(футбол|football)[.\s]*', '', raw_bracket, flags=re.I).strip()
    return clean if clean else "Інше"

def is_football(text: str) -> bool:
    lo = text.lower()
    if any(s in lo for s in NON_FOOTBALL): return False
    return True


# ─── ПАРСИНГ LIVETV LIVE ─────────────────────────────────────────────────────
@st.cache_data(ttl=90)
def load_livetv_live():
    """Завантажує ТІЛЬКИ live-матчі з livetv.sx/alllivesports/."""
    ck = f"ltv_live_{TZ_SITE}"
    cached = cache_get(ck, ttl=90)
    if cached: return cached

    live_ids: set = set()
    live_scores: dict = {}
    try:
        r = requests.get("https://livetv.sx/alllivesports/",
                         timeout=20, headers=HDR, verify=False)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        for img in soup.find_all("img", src=re.compile(r"live\.gif", re.I)):
            nxt = img.find_next_sibling("span", class_="live")
            if not nxt:
                parent = img.parent
                nxt = parent.find("span", class_="live") if parent else None
            if not nxt: continue
            txt = nxt.get_text(strip=True)
            mm = re.search(r"^(\d{1,3}):(\d{1,3})$", txt)

            container = img.find_parent("td") or img.find_parent("div") or img.parent
            a = None
            node = container
            for _ in range(5):
                if node is None: break
                a = node.find("a", href=re.compile(r"/eventinfo/\d+"))
                if a: break
                node = node.parent
            if not a: continue
            m2 = re.search(r"/eventinfo/(\d+)", a["href"])
            if not m2: continue
            eid = m2.group(1)
            live_ids.add(eid)
            if mm:
                g1, g2 = int(mm.group(1)), int(mm.group(2))
                live_scores[eid] = f"{g1}:{g2}"
    except Exception as e:
        print(f"livetv live: {e}", flush=True)

    result = {"ids": list(live_ids), "scores": live_scores}
    cache_set(ck, result)
    return result


# ─── ПАРСИНГ LIVETV РОЗКЛАД ──────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_livetv():
    ck = f"ltv10_{TZ_SITE}"
    cached = cache_get(ck, ttl=600)
    if cached: return cached

    html = None
    for attempt, (tout, delay) in enumerate([(30,0),(45,3),(60,5)], 1):
        try:
            if delay:
                import time; time.sleep(delay)
            r = requests.get("https://livetv.sx/allupcomingsports/1/",
                             timeout=tout, headers=HDR, verify=False)
            r.raise_for_status()
            html = r.text
            break
        except Exception as e:
            print(f"livetv attempt {attempt}: {e}", flush=True)

    if not html:
        cache_set(ck, {"top":[], "all":[]})
        return {"top":[], "all":[]}

    soup = BeautifulSoup(html, "html.parser")
    year = datetime.now().year

    top_table = None
    schedule_table = None

    sltitle = soup.find("span", class_="sltitle", string=re.compile(r"^Футбол$"))
    if sltitle:
        container_td = sltitle.find_parent("td", attrs={"valign": "top"})
        if not container_td:
            container_td = sltitle.find_parent("td")
        if container_td:
            tables = container_td.find_all("table", recursive=False)
            print(f"  Футбольний блок: {len(tables)} таблиць", flush=True)
            for t in tables:
                ct2 = t.find_all("td", colspan="2")
                if not ct2: continue
                has_top_bg = bool(t.find("td", attrs={"bgcolor": "#fffcec"}))
                if has_top_bg and top_table is None:
                    top_table = t
                elif not has_top_bg:
                    if schedule_table is None or len(str(t)) > len(str(schedule_table)):
                        schedule_table = t

            print(f"  top_table: {len(str(top_table)) if top_table else 0} байт "
                  f"({len(top_table.find_all('td', colspan='2')) if top_table else 0} матчів), "
                  f"schedule_table: {len(str(schedule_table)) if schedule_table else 0} байт "
                  f"({len(schedule_table.find_all('td', colspan='2')) if schedule_table else 0} матчів)",
                  flush=True)

    meta_scope = soup
    if top_table or schedule_table:
        from bs4 import BeautifulSoup as BS4
        combined_html = ""
        if top_table: combined_html += str(top_table)
        if schedule_table: combined_html += str(schedule_table)
        meta_scope = BS4(combined_html, "html.parser")

    event_meta: dict = {}

    NON_SPORT_PREFIXES = (
        "хоккей", "баскетбол", "теннис", "волейбол", "бокс",
        "гонки", "хоккей с мячом", "футзал", "гандбол", "регби-лига",
        "регби-союз", "регби", "зимний спорт", "бейсбол", "керлинг",
        "пляжный волейбол", "водное поло", "пляжный футбол",
        "американский футбол", "бильярд", "дартс", "бадминтон",
        "флорбол", "гольф", "велоспорт", "крикет", "тяжёлая атлетика",
        "австралийский футбол", "конный спорт", "единоборства",
        "триатлон", "нетбол", "мма",
        "futsal", "мини-футбол", "мінi-футбол", "міні-футбол",
        "снукер", "биатлон", "лыж", "фигурн",
        "борьб", "дзюдо", "карате", "плаван",
        "атлетика", "фехтование", "парусный", "гребля", "стрельба",
        "ралли", "formula", "формула", "nascar", "мото",
    )

    for a_tag in meta_scope.find_all("a", href=re.compile(r"/eventinfo/\d+")):
        m = re.search(r"/eventinfo/(\d+)", a_tag["href"])
        if not m: continue
        eid = m.group(1)
        if eid in event_meta: continue

        td_colspan = a_tag.find_parent("td", attrs={"colspan": "2"})
        sport_img = td_colspan.find("img", alt=True) if td_colspan else None
        sport_alt = sport_img.get("alt", "") if sport_img else ""
        sport_alt_lo = sport_alt.lower()

        if any(sport_alt_lo.startswith(p) for p in NON_SPORT_PREFIXES):
            continue

        parent = a_tag.parent
        evdesc = None
        for _ in range(7):
            if parent is None: break
            evdesc = parent.find("span", class_="evdesc")
            if evdesc: break
            parent = parent.parent
        if not evdesc: continue

        evtext = evdesc.get_text(" ", strip=True)

        if sport_alt_lo.startswith("футбол"):
            league_raw = re.sub(r"^футбол[.\s]*", "", sport_alt, flags=re.I).strip()
        else:
            lm = re.search(r"\(([^)]{2,90})\)\s*$", evtext)
            league_raw = lm.group(1).strip() if lm else ""
            if not is_football(league_raw): continue
            nf_starts = ["баскетбол","хоккей","теннис","волейбол","бокс","регби",
                         "гонки","велос","плаван","атлет","борьб"]
            if any(league_raw.lower().startswith(s) for s in nf_starts): continue

        league = map_league(league_raw)

        league_logo = None
        if sport_img:
            src = sport_img.get("src", "")
            lf = re.search(r"/([\w]+\.gif)$", src)
            if lf: league_logo = f"https://livetv.sx/i/{lf.group(1)}"

        event_meta[eid] = {
            "league_raw": league_raw,
            "league": league,
            "evtext": evtext,
            "league_logo": league_logo,
        }

    # ── Крок 2: Парсимо <td colspan="2"> ─────────────────────────────────────
    seen: set = set()
    top_list: list = []
    all_list: list = []

    def parse_td(td, is_top=False):
        a = td.find("a", href=re.compile(r"/eventinfo/\d+"))
        if not a or not a.get_text(strip=True): return None

        href = a["href"]
        if not href.startswith("http"): href = "https://livetv.sx" + href
        m = re.search(r"/eventinfo/(\d+)", href)
        if not m: return None
        eid = m.group(1)
        if eid in seen: return None

        meta = event_meta.get(eid)
        if not meta: return None
        seen.add(eid)

        title = a.get_text(strip=True)
        if not re.search(r"[–—]", title) or len(title) < 5: return None

        evtext = meta["evtext"]

        dt = None
        tm = re.search(r"(\d{1,2})\s+(\w+)\s+в\s+(\d{1,2}):(\d{2})", evtext)
        if tm:
            mon = MONTHS_RU.get(tm.group(2).lower())
            if mon:
                try:
                    dt = datetime(year, mon, int(tm.group(1)),
                                  int(tm.group(3)), int(tm.group(4)))
                except: pass
        if dt is None:
            tm2 = re.search(r"(\d{1,2}):(\d{2})", evtext)
            if tm2:
                try:
                    n = datetime.now()
                    dt = n.replace(hour=int(tm2.group(1)),
                                   minute=int(tm2.group(2)), second=0, microsecond=0)
                except: pass
        if dt is None: return None

        td_row = td.find_parent("tr") or td
        td_html = str(td_row)
        has_live_gif = "live.gif" in td_html or "liveicon" in td_html.lower()

        inline_score = None
        if has_live_gif:
            for el in td_row.find_all(["td", "span", "div"]):
                if el.find("a"): continue
                txt = el.get_text(strip=True)
                mm = re.fullmatch(r"(\d{1,2})\s*[:\-]\s*(\d{1,2})", txt)
                if mm:
                    inline_score = f"{mm.group(1)}:{mm.group(2)}"
                    break

        delta = (datetime.now() - dt).total_seconds() / 60
        if has_live_gif:
            status = "live"
        elif 0 <= delta <= 115:
            status = "live"
        elif delta > 115:
            status = "finished"
        else:
            status = "upcoming"

        # На сторінці розкладу логотипів команд немає — залишаємо None,
        # вони будуть завантажені окремо через fetch_event_page в parser_job.py
        t1_logo = t2_logo = None

        t1n, t2n = title, ""
        mp = re.match(r"^(.+?)\s*[–—]\s*(.+)$", title.strip())
        if mp: t1n, t2n = mp.group(1).strip(), mp.group(2).strip()

        league = meta["league"]
        league_raw = meta["league_raw"]

        always = (
            league in PRIORITY_LEAGUES or
            any(k in league_raw.lower() for k in ["евро", "чемпионат мира", "world cup"]) or
            any(k in title.lower() for k in UKR_KW)
        )

        return {
            "time": dt.isoformat(), "title": title,
            "team1": t1n, "team2": t2n,
            "url": href, "event_id": eid,
            "status": status, "league": league, "league_raw": league_raw,
            "t1_logo": t1_logo, "t2_logo": t2_logo,
            "score": inline_score, "is_top": is_top, "always_show": always,
            "league_logo": meta.get("league_logo"),
        }

    # Топ-матчі
    top_ids: set = set()
    top_search_scope = top_table if top_table else soup
    b = top_search_scope.find(string=re.compile(r"Главные матчи", re.I))
    if not b and top_table is None:
        b = soup.find(string=re.compile(r"Главные матчи", re.I))
    if b:
        tbl = b.find_parent("table")
        if tbl:
            for td in tbl.find_all("td", colspan="2"):
                res = parse_td(td, is_top=True)
                if res:
                    top_ids.add(res["event_id"])
                    top_list.append(res)
    elif top_table:
        for td in top_table.find_all("td", colspan="2"):
            res = parse_td(td, is_top=True)
            if res:
                top_ids.add(res["event_id"])
                top_list.append(res)

    all_search_scope = schedule_table if schedule_table else meta_scope
    for td in all_search_scope.find_all("td", colspan="2"):
        res = parse_td(td, is_top=False)
        if res and res["event_id"] not in top_ids:
            all_list.append(res)

    result = {"top": top_list, "all": all_list}
    cache_set(ck, result)
    print(f"livetv: top={len(top_list)}, all={len(all_list)}", flush=True)
    return result


# ─── ЛОГОТИПИ З СТОРІНКИ МАТЧУ ───────────────────────────────────────────────
def fetch_logos_for_event(event_id: str, event_url: str) -> tuple[str | None, str | None]:
    """
    Завантажує сторінку матчу і повертає (t1_logo_url, t2_logo_url).
    Використовує файловий кеш щоб не запитувати двічі.
    Порядок пошуку:
      1. JSON-LD (application/ld+json) — найнадійніше, абсолютні CDN URLs
      2. <img itemprop="image"> — fallback
    """
    ck = f"logos_{event_id}"
    cached = cache_get(ck, ttl=86400 * 30)  # логотипи не змінюються — кешуємо на 30 днів
    if cached:
        return cached.get("t1"), cached.get("t2")

    t1 = t2 = None
    try:
        r = requests.get(event_url, timeout=10, headers=HDR, verify=False)
        r.raise_for_status()
        s = BeautifulSoup(r.text, "html.parser")

        # ── Спосіб 1: JSON-LD ─────────────────────────────────────────────────
        for script in s.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                images = data.get("image", [])
                if isinstance(images, list) and len(images) >= 2:
                    t1 = images[0] if images[0].startswith("http") else None
                    t2 = images[1] if images[1].startswith("http") else None
                    if t1 and t2:
                        break
            except Exception:
                pass

        # ── Спосіб 2: <img itemprop="image"> ─────────────────────────────────
        if not t1 or not t2:
            logos = []
            for img in s.find_all("img", attrs={"itemprop": "image"}):
                src = img.get("src", "").strip()
                # Пропускаємо відносні шляхи (збережені локально браузером)
                if not src.startswith("http"):
                    # Намагаємось реконструювати CDN URL з імені файлу
                    fname = src.split("/")[-1]
                    if re.match(r"^\d+\.gif$", fname):
                        src = f"https://cdn.livetv873.me/img/teams/fullsize/ods/{fname}"
                    else:
                        continue
                if src not in logos:
                    logos.append(src)
            if logos and not t1:
                t1 = logos[0]
            if len(logos) > 1 and not t2:
                t2 = logos[1]

        # ── Спосіб 3: CDN URLs напряму з тексту HTML ─────────────────────────
        if not t1 or not t2:
            cdn_logos = re.findall(
                r'https://cdn\.livetv\d+\.me/img/teams/[^\s"\'<>]+\.gif',
                r.text,
            )
            # Фільтруємо унікальні
            seen_cdn = []
            for u in cdn_logos:
                if u not in seen_cdn:
                    seen_cdn.append(u)
            if seen_cdn and not t1:
                t1 = seen_cdn[0]
            if len(seen_cdn) > 1 and not t2:
                t2 = seen_cdn[1]

    except Exception as e:
        print(f"  fetch_logos {event_id}: {e}", flush=True)

    cache_set(ck, {"t1": t1, "t2": t2})
    return t1, t2


# ─── РАХУНОК ЗІ СТОРІНКИ МАТЧУ ──────────────────────────────────────────────
def fetch_event_page(event_id: str, event_url: str, status: str) -> dict:
    ttl = 90 if status == "live" else (172800 if status == "finished" else 21600)
    ck = f"ep2_{event_id}"
    cached = cache_get(ck, ttl=ttl)
    if cached: return cached

    result = {"score": None, "t1": None, "t2": None}
    try:
        r = requests.get(event_url, timeout=10, headers=HDR, verify=False)
        r.raise_for_status()
        s = BeautifulSoup(r.text, "html.parser")

        score = None
        for img in s.find_all("img", src=re.compile(r"live\.gif", re.I)):
            td = img.find_parent("td")
            if not td: continue
            a = td.find("a", href=re.compile(rf"/eventinfo/{event_id}"))
            if not a: continue
            span = td.find("span", class_="live")
            if not span: continue
            txt = span.get_text(strip=True)
            mm = re.search(r"^(\d{1,3}):(\d{1,3})$", txt)
            if mm:
                g1, g2 = int(mm.group(1)), int(mm.group(2))
                if g1 <= 30 and g2 <= 30:
                    score = f"{g1}:{g2}"
            break

        for sel in ["td.score", "span.score", ".lscore", ".mscore", ".score",
                    "[class*='score']", "td.lbc", "span.lbc", "[class*='result']"]:
            try:
                for el in s.select(sel):
                    txt = el.get_text(strip=True)
                    m2 = re.search(r"(\d{1,3})\s*[:\-]\s*(\d{1,3})", txt)
                    if m2:
                        h, mn = int(m2.group(1)), int(m2.group(2))
                        if h <= 30 and mn <= 30:
                            score = f"{h}:{mn}"; break
                if score: break
            except: pass

        if score is None:
            title_tag = s.find("title")
            if title_tag:
                m2 = re.search(r"\b(\d{1,2})\s*[:\-]\s*(\d{1,2})\b", title_tag.get_text())
                if m2:
                    h, mn = int(m2.group(1)), int(m2.group(2))
                    if h <= 30 and mn <= 30:
                        score = f"{h}:{mn}"

        if score is None:
            for el in s.find_all(string=True):
                t = el.strip()
                if re.fullmatch(r"\d{1,2}\s*[:\-]\s*\d{1,2}", t):
                    m2 = re.search(r"(\d{1,2})\s*[:\-]\s*(\d{1,2})", t)
                    if m2:
                        h, mn = int(m2.group(1)), int(m2.group(2))
                        if h <= 30 and mn <= 30:
                            score = f"{h}:{mn}"; break

        result["score"] = score

        # Логотипи через JSON-LD (найнадійніше)
        logos = []
        for script in s.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                images = data.get("image", [])
                if isinstance(images, list):
                    for img_url in images:
                        if img_url.startswith("http") and img_url not in logos:
                            logos.append(img_url)
                if len(logos) >= 2:
                    break
            except Exception:
                pass

        # Fallback: <img itemprop="image">
        if len(logos) < 2:
            for img in s.find_all("img", attrs={"itemprop": "image"}):
                src = img.get("src", "").strip()
                if not src.startswith("http"):
                    fname = src.split("/")[-1]
                    if re.match(r"^\d+\.gif$", fname):
                        src = f"https://cdn.livetv873.me/img/teams/fullsize/ods/{fname}"
                    else:
                        continue
                if src not in logos:
                    logos.append(src)

        # Fallback: CDN URLs з тексту HTML
        if len(logos) < 2:
            cdn_logos = re.findall(
                r'https://cdn\.livetv\d+\.me/img/teams/[^\s"\'<>]+\.gif',
                r.text,
            )
            for u in cdn_logos:
                if u not in logos:
                    logos.append(u)

        if logos: result["t1"] = logos[0]
        if len(logos) > 1: result["t2"] = logos[1]

    except Exception as e:
        print(f"  event {event_id}: {e}", flush=True)

    if status == "upcoming":
        result["score"] = None
    cache_set(ck, result)
    return result


# ─── GOOOOL365 ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=900)
def load_gooool_urls():
    ck = "gool3"
    cached = cache_get(ck, ttl=900)
    if cached: return cached
    result = []
    try:
        r = requests.get("https://gooool365.org/online/", timeout=15,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tn in soup.find_all(string=re.compile(r"^\d{1,2}:\d{2}$")):
            node = tn.parent
            a_tag = None
            for _ in range(8):
                if node is None: break
                a = node.find("a", href=re.compile(r"/online/\d+"))
                if a: a_tag = a; break
                node = node.find_next_sibling() or getattr(node, "parent", None)
            if not a_tag: continue
            href = a_tag.get("href", "")
            if not href.startswith("http"): href = "https://gooool365.org" + href
            result.append({"title": a_tag.get_text(strip=True), "url": href})
    except Exception as e:
        print(f"gooool: {e}", flush=True)
    cache_set(ck, result)
    return result


def find_gooool(t1: str, t2: str, glist: list) -> str | None:
    if not t1 or not t2: return None
    TR = {"байер л":"байер","будё/глимт":"будё-глимт",
          "манчестер сити":"ман сити","манчестер юнайтед":"ман юнайтед",
          "псж":"пари сен-жермен","пари сен-жермен":"псж"}
    def variants(n):
        n = n.lower().strip(); v = {n}
        for k, val in TR.items():
            if k in n: v.add(n.replace(k, val))
            if val in n: v.add(n.replace(val, k))
        return v
    def sim(a, b):
        for va in variants(a):
            for vb in variants(b):
                if len(va) >= 4 and len(vb) >= 4 and (va[:5] in vb or vb[:5] in va):
                    return True
        return False
    for gm in glist:
        mp = re.match(r"^(.+?)\s*[-—–]\s*(.+)$", gm["title"].strip())
        if not mp: continue
        g1, g2 = mp.group(1).strip(), mp.group(2).strip()
        if (sim(t1,g1) and sim(t2,g2)) or (sim(t1,g2) and sim(t2,g1)):
            return gm["url"]
    return None


def fetch_score_from_gooool(gurl: str) -> str | None:
    if not gurl: return None
    ck = f"gscore_{hashlib.md5(gurl.encode()).hexdigest()[:10]}"
    cached = cache_get(ck, ttl=60)
    if cached is not None: return cached.get("score")
    try:
        r = requests.get(gurl, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        s = BeautifulSoup(r.text, "html.parser")
        for sel in [".score", ".result", "[class*='score']", "[class*='result']",
                    "span.live-score", "div.score", "td.score"]:
            for el in s.select(sel):
                txt = el.get_text(strip=True)
                mm = re.search(r"(\d{1,2})\s*[:\-]\s*(\d{1,2})", txt)
                if mm:
                    h, a = int(mm.group(1)), int(mm.group(2))
                    if h <= 20 and a <= 20:
                        score = f"{h}:{a}"
                        cache_set(ck, {"score": score})
                        return score
        title_tag = s.find("title")
        if title_tag:
            mm = re.search(r"(\d{1,2})\s*[:\-]\s*(\d{1,2})", title_tag.get_text())
            if mm:
                h, a = int(mm.group(1)), int(mm.group(2))
                if h <= 20 and a <= 20:
                    score = f"{h}:{a}"
                    cache_set(ck, {"score": score})
                    return score
    except: pass
    cache_set(ck, {"score": None})
    return None
