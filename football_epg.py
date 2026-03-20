"""
Sporter.ua — Football EPG
Streamlit app: python -m streamlit run football_epg.py
"""
import streamlit as st
import requests, re, os, json, hashlib, base64, urllib.parse
from datetime import datetime, timedelta
from collections import defaultdict
from bs4 import BeautifulSoup
import urllib3; urllib3.disable_warnings()

st.set_page_config(page_title="Sporter", layout="wide", initial_sidebar_state="auto")

# ─── ШЛЯХИ ───────────────────────────────────────────────────────────────────
BASE      = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE, "epg_cache")
LOGOS_DIR = os.path.join(CACHE_DIR, "logos")
CFG_FILE     = os.path.join(BASE, "epg_settings.json")
LEAGUES_FILE = os.path.join(BASE, "epg_leagues.json")  # накопительный, не сбрасывается
for d in (CACHE_DIR, LOGOS_DIR): os.makedirs(d, exist_ok=True)

# Очищаємо старі кеші рахунків і розкладу щоб час завжди перераховувався
_now_ts = datetime.now().timestamp()
for _f in os.listdir(CACHE_DIR):
    if _f.startswith("ep2_") or _f.startswith("ltv_live_") or _f.startswith("ltv10_"):
        _fp = os.path.join(CACHE_DIR, _f)
        try:
            if _now_ts - os.path.getmtime(_fp) > 300:  # старіше 5 хв
                os.remove(_fp)
        except: pass

HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7"
}
TZ_SITE = 3   # livetv.sx відображає час UTC+3

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

# ─── НАЛАШТУВАННЯ ────────────────────────────────────────────────────────────
DEFAULT_CFG = {
    "tz_offset": 3,
    "show_score": True,
    "dark_theme": True,
    "active_leagues": [],
    "show_interesting": True,
    "boost_ukraine": True,
}

# ─── ТОП КОМАНДИ СВІТУ: РЕЙТИНГ ЗАЦІКАВЛЕНОСТІ 1-5 ЗІРОК ───────────────────
# Джерела: IFFHS 2025, Opta Power Rankings, UEFA коефіцієнти, Elo ratings
# Ключ — підрядок (lower), значення — кількість зірок (1..5)
# Чим більше зірок — тим вище в секції "Головні матчі дня"
TOP_CLUBS = {
    # ★★★★★  Топ-12: абсолютна еліта, найбільший глобальний інтерес
    "реал мадрид": 5, "пари сен-жермен": 5, "псж": 5,
    "манчестер сити": 5, "ман сити": 5,
    "арсенал": 5, "барселона": 5,
    "бавария": 5, "баварія": 5,
    "ливерпуль": 5, "ліверпуль": 5,
    "манчестер юнайтед": 5, "ман юнайтед": 5,
    "челси": 5,

    # ★★★★  Топ-13..35: постійні учасники ЛЧ, великі клуби
    "атлетико": 4, "атлетіко": 4,
    "інтер": 4, "ювентус": 4,
    "боруссия дортмунд": 4, "боруссія": 4,
    "аталанта": 4,
    "байер": 4, "байєр": 4, "леверкузен": 4,
    "тоттенхем": 4,
    "ньюкасл": 4,
    "бенфіка": 4, "бенфика": 4,
    "порто": 4,
    "аякс": 4,
    "милан": 4,
    "наполи": 4, "наполь": 4,
    "рома": 4, "ромa": 4,
    "реал сосьедад": 4,
    "монако": 4, "марсель": 4,
    "лейпциг": 4,
    "астон вілла": 4,
    "спортінг": 4,

    # ★★★  Топ-36..65: сильні клуби з великою аудиторією
    "флорентина": 3, "фіорентина": 3,
    "лаціо": 3, "торіно": 3,
    "севілья": 3, "вільярреал": 3,
    "бетіс": 3, "валенсія": 3, "жирона": 3,
    "брюгге": 3, "псв": 3, "феєнорд": 3,
    "ліон": 3, "лілль": 3,
    "вест хем": 3, "брайтон": 3,
    "галатасарай": 3, "фенербахче": 3,
    "селтик": 3, "рейнджерс": 3,
    "шахтар": 3, "шахтар донецьк": 3, "шахтер": 3, "шахтер донецк": 3,
    "динамо київ": 3, "динамо киев": 3,
    "рівер плейт": 3, "бока хуніорс": 3,
    "фламенго": 3, "палмейрас": 3,
    "аль-хіляль": 3, "аль-хилаль": 3,
    "аль-нассер": 3, "аль-наср": 3,
    "флуміненсе": 3, "атлетіко мінейро": 3,
    "штутгарт": 3, "фрайбург": 3, "хоффенхайм": 3,
    "ніцца": 3, "ренн": 3,
    "аз алкмаар": 3, "брага": 3,

    # ★★  Топ-66..85: відомі клуби, регіональний інтерес
    "евертон": 2, "лестер": 2, "ноттінгем": 2,
    "брентфорд": 2, "кристал пелас": 2,
    "вольфсбург": 2, "уніон берлін": 2, "майнц": 2,
    "саутгемптон": 2, "лідс": 2,
    "страсбур": 2, "лансе": 2,
    "болонья": 2, "удінезе": 2, "дженоа": 2,
    "осасуна": 2, "гімарайнш": 2,
    "бешикташ": 2, "трабзонспор": 2,
    "аль-іттіхад": 2, "аль-иттихад": 2, "аль-ахлі": 2, "аль-ахли": 2,
    "зеніт": 2, "краснодар": 2,
    "копенгаген": 2, "мідтьюлланн": 2,
    "зальцбург": 2, "рапід відень": 2,
    "партізан": 2, "слован": 2,
    "вікторія пльзень": 2,
    "монтеррей": 2, "пачука": 2, "крус асуль": 2,
    "атланта": 2, "лос-анджелес фк": 2, "lafc": 2,

    # ★  Топ-86..100+: команди що набирають популярність або мають локальний інтерес
    "аугсбург": 1, "уніон берлін": 1,
    "жирона": 1,
    "монца": 1, "сасуолo": 1,
    "мідтьюлланн": 1, "брондбю": 1,
    "мольде": 1, "русенборг": 1,
    "штурм ґрац": 1,
    "гремьо": 1, "сан-паулу": 1,
    "індепендьєнте": 1, "расінг": 1,
    "нью-йорк": 1, "сіетл": 1, "портленд": 1,
    "ворскла": 1, "динамо": 1,
    "марко": 1,
    # АПЛ — всі команди мають мінімум ★1
    "борнмут": 1, "іпсвіч": 1, "фулем": 1, "вулвс": 1, "вулвергемптон": 1,
    "вест хем": 1,
}

# Ключові слова молодіжних/резервних матчів — рейтинг обнуляємо
YOUTH_KEYWORDS = [
    "до 19", "до 21", "до 23", "до 17", "до 16", "до 15", "до 14",
    "u19", "u21", "u23", "u17", "u16", "u18",
    "молодь", "молодёжн", "резерв", "youth", "reserve", "юніор",
    "b team", "ii ", " ii", "друг", "аматор",
]

def club_rating(name: str) -> int:
    """Повертає рейтинг зацікавленості команди (0 якщо не в списку)"""
    nl = name.lower()
    best = 0
    for club, rating in TOP_CLUBS.items():
        if club in nl:
            best = max(best, rating)
    return best

def match_interest_score(team1: str, team2: str, league: str = "") -> int:
    """Рейтинг матчу = максимум з рейтингів двох команд (1-5, 0 якщо не цікаво).
    Молодіжні/резервні матчі завжди отримують 0.
    Якщо увімкнено BOOST_UKRAINE — українські команди в глобальних турнірах мінімум ★★★."""
    combined_lower = (team1 + " " + team2).lower()
    if any(kw in combined_lower for kw in YOUTH_KEYWORDS):
        return 0
    base = max(club_rating(team1), club_rating(team2))
    if BOOST_UKRAINE and league in UKR_BOOST_LEAGUES:
        if any(kw in combined_lower for kw in UKR_TEAM_KW):
            base = max(base, 3)
    return base

def is_interesting_match(team1: str, team2: str) -> bool:
    """Повертає True якщо хоча б одна з команд є топ-клубом"""
    return match_interest_score(team1, team2) > 0

def load_cfg():
    d = dict(DEFAULT_CFG)
    if os.path.exists(CFG_FILE):
        try: d.update(json.load(open(CFG_FILE, encoding="utf-8")))
        except: pass
    return d

def save_cfg(d):
    json.dump(d, open(CFG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def load_known_leagues():
    """Загружает накопительный список лиг из отдельного файла."""
    if os.path.exists(LEAGUES_FILE):
        try: return set(json.load(open(LEAGUES_FILE, encoding="utf-8")))
        except: pass
    return set()

def save_known_leagues(leagues: set):
    """Сохраняет накопительный список лиг — только добавляет, никогда не удаляет."""
    existing = load_known_leagues()
    merged = sorted(existing | leagues)
    json.dump(merged, open(LEAGUES_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

CFG = load_cfg()
TZ                 = CFG["tz_offset"]
SHOW_SCORE         = CFG["show_score"]
DARK               = CFG["dark_theme"]
ACTIVE_LGS         = set(CFG.get("active_leagues", []))
SHOW_INTERESTING   = CFG.get("show_interesting", True)
BOOST_UKRAINE      = CFG.get("boost_ukraine", True)

# ─── ЛІГИ: СУВОРИЙ МАППІНГ ───────────────────────────────────────────────────
# Кожен запис: (список обов'язкових підрядків, назва ліги українською)
# Порядок важливий — перший збіг перемагає.
# Формат з livetv: "(Країна. Назва)" або "(Назва турніру)"
MONTHS_RU = {
    "января":1,"февраля":2,"марта":3,"апреля":4,"мая":5,"июня":6,
    "июля":7,"августа":8,"сентября":9,"октября":10,"ноября":11,"декабря":12
}

# Маппінг: (ключові слова які ВСІМА мають бути в рядку, назва)
# Кожен елемент — (list_of_any_match_kw, league_name)
# Ми перевіряємо: any(kw in text for kw in list)
LEAGUE_MAP = [
    # ── UEFA клубные ─────────────────────────────────────────────────────────
    (["лига чемпионов", "champions league", "ucl"],                 "Лига чемпионов"),
    (["лига европы", "europa league", "uel"],                       "Лига Европы"),
    (["лига конференций", "conference league"],                      "Лига конференций"),
    (["юношеская лига уефа", "youth league"],                       "Юнош. лига УЕФА"),
    # ── UEFA сборные ─────────────────────────────────────────────────────────
    (["лига наций", "nations league"],                              "Лига наций"),
    (["чемпионат европы", "евро-20", "евро-21", "квалификация евро","euro qualif"], "Евро квал."),
    (["чемпионат мира", "world cup", "квалификация чм"],            "ЧМ квал."),
    # ── Англия ───────────────────────────────────────────────────────────────
    (["англия. премьер", "англия. прем", "premier league"],         "АПЛ"),
    (["англия. чемпионшип", "championship"],                        "Чемпионшип"),
    (["кубок англии", "fa cup"],                                     "Кубок Англии"),
    (["англия. лига 1", "england. league one"],                     "Лига 1 Англия"),
    (["англия. лига 2", "england. league two"],                     "Лига 2 Англия"),
    # ── Испания ──────────────────────────────────────────────────────────────
    (["испания. примера", "испания. ла лига", "la liga"],           "Ла Лига"),
    (["испания. сегунда", "segunda division"],                      "Сегунда"),
    (["испания. кубок", "copa del rey"],                            "Кубок Испании"),
    # ── Германия ─────────────────────────────────────────────────────────────
    (["германия. бундеслига", "германия. 1. бундес", "bundesliga"],  "Бундеслига"),
    (["германия. 2. бундес", "2. bundesliga"],                      "2. Бундеслига"),
    (["германия. кубок", "dfb-pokal"],                              "Кубок Германии"),
    # ── Италия ───────────────────────────────────────────────────────────────
    (["италия. серия а", "serie a"],                                "Серия А"),
    (["италия. серия б", "serie b"],                                "Серия Б"),
    (["италия. кубок", "coppa italia"],                             "Кубок Италии"),
    # ── Франция ──────────────────────────────────────────────────────────────
    (["франция. лига 1", "ligue 1"],                                "Лига 1 Франция"),
    (["франция. лига 2", "ligue 2"],                                "Лига 2 Франция"),
    (["франция. кубок", "coupe de france"],                         "Кубок Франции"),
    # ── Украина ──────────────────────────────────────────────────────────────
    (["украина. премьер", "упл"],                                   "УПЛ"),
    (["украина. кубок", "кубок украины"],                           "Кубок Украины"),
    (["украина. первая", "украина. 1. лига"],                       "Первая лига Укр"),
    # ── Нидерланды ───────────────────────────────────────────────────────────
    (["нидерланды. эредивизи", "eredivisie"],                       "Эредивизи"),
    # ── Португалия ───────────────────────────────────────────────────────────
    (["португалия. примейра", "primeira liga"],                     "Примейра"),
    # ── Бельгия ──────────────────────────────────────────────────────────────
    (["бельгия. жюпилер", "jupiler pro league"],                    "Жюпилер"),
    # ── Турция ───────────────────────────────────────────────────────────────
    (["süper lig", "super lig"],                                    "Суперлига Тур"),
    # ── Шотландия ────────────────────────────────────────────────────────────
    (["шотландия. премьер", "scottish premiership"],                "Шотландия Пр"),
    # ── США ──────────────────────────────────────────────────────────────────
    (["млс", "major league soccer"],                                "МЛС"),
    (["сша. открытый кубок", "usa. open cup", "u.s. open cup"],     "США. Открытый кубок"),
    (["сша. юзл", "уsl championship", "usl"],                       "США. USL"),
    (["сша. женщины", "nwsl"],                                       "США. Женщины"),
    (["конкакаф", "concacaf champions"],                             "КОНКАКАФ"),
    # ── Саудовская Аравия ────────────────────────────────────────────────────
    (["саудовская аравия. про", "saudi pro league"],                "Саудовская Пр"),
    # ── Аргентина ────────────────────────────────────────────────────────────
    (["аргентина. примера", "аргентина. суперлига"],                "Примера Арг"),
    (["аргентина. профессиональная", "аргентина. проф"],            "Аргентина. Проф лига"),
    # ── Бразилия ─────────────────────────────────────────────────────────────
    (["бразилия. серия а", "brasileirao"],                          "Серия А Бр"),
    (["бразилия. кубок", "copa do brasil", "бразилия. кубок"],     "Кубок Бразилии"),
    (["бразилия. серия б"],                                         "Серия Б Бр"),
    (["бразилия. серия в"],                                         "Серия В Бр"),
    (["бразилия. серия г"],                                         "Серия Г Бр"),
    (["бразилия."],                                                  "Бразилия. Другое"),
    # ── Россия ───────────────────────────────────────────────────────────────
    (["россия. рпл", "россия. премьер"],                            "РПЛ"),
    # ── Другие ───────────────────────────────────────────────────────────────
    (["греция. суперлига", "super league греция"],                  "Суперлига Гр"),
    (["хорватия. хнл", "hnl"],                                      "ХНЛ"),
    (["польша. экстраклас", "ekstraklasa"],                         "Экстракласа"),
    (["австрия. бундеслига", "austria. bundesliga"],                "Бундеслига Авс"),
    (["чехия. фортуна", "fortuna liga"],                            "Фортуна Лига"),
    (["нидерланды. кередивизи", "keuken"],                         "Кередивизи"),
    (["израиль. премьер"],                                          "Премьерлига Изр"),
    (["дания. суперлига", "superliga"],                             "Суперлига Дан"),
    (["швеция. алсвенскан", "allsvenskan"],                        "Алсвенскан"),
    (["норвегия. элитесерен", "eliteserien"],                      "Элитесерен"),
    (["швейцария. суперлига", "swiss super league"],               "Суперлига Шв"),
    (["румыния. суперлига"],                                        "Суперлига Рум"),
    (["катар. лига звезд", "qatar stars"],                         "Лига звёзд Кат"),
    # ── Catch-all по странам ─────────────────────────────────────────────────
    (["аргентина."],   "Аргентина"),
    (["колумбия."],    "Колумбия"),
    (["чили."],        "Чили"),
    (["мексика."],     "Мексика"),
    (["перу."],        "Перу"),
    (["боливия."],     "Боливия"),
    (["эквадор."],     "Эквадор"),
    (["уругвай."],     "Уругвай"),
    (["венесуэла."],   "Венесуэла"),
    (["парагвай."],    "Парагвай"),
    (["япония."],      "Япония"),
    (["китай."],       "Китай"),
    (["южная корея.", "корея."], "Корея"),
    (["австралия."],   "Австралия"),
    (["иран."],        "Иран"),
    (["ирак."],        "Ирак"),
    (["индия."],       "Индия"),
    (["египет."],      "Египет"),
    (["марокко."],     "Марокко"),
    (["нигерия."],     "Нигерия"),
    (["гана."],        "Гана"),
    (["финляндия."],   "Финляндия"),
    (["шотландия."],   "Шотландия"),
    (["ирландия."],    "Ирландия"),
    (["сербия."],      "Сербия"),
    (["словакия."],    "Словакия"),
    (["словения."],    "Словения"),
    (["болгария."],    "Болгария"),
    (["венгрия."],     "Венгрия"),
    (["босния."],      "Босния"),
    (["казахстан."],   "Казахстан"),
    (["беларусь."],    "Беларусь"),
    (["литва."],       "Литва"),
    (["латвия."],      "Латвия"),
    (["эстония."],     "Эстония"),
    (["кипр."],        "Кипр"),
    (["мальта."],      "Мальта"),
    (["люксембург."],  "Люксембург"),
    (["северная ирландия."], "Сев. Ирландия"),
    (["уэльс."],       "Уэльс"),
    (["исландия."],    "Исландия"),
    (["фарерские."],   "Фарерские"),
    (["азербайджан."], "Азербайджан"),
    (["грузия."],      "Грузия"),
    (["армения."],     "Армения"),
    (["таиланд."],     "Таиланд"),
    (["вьетнам."],     "Вьетнам"),
    (["индонезия."],   "Индонезия"),
    (["малайзия."],    "Малайзия"),
    (["филиппины."],   "Филиппины"),
    (["южная африка.", "юар."], "ЮАР"),
    (["конкакаф", "concacaf"],  "КОНКАКАФ"),
    (["либертадорес", "libertadores"], "Копа Либертадорес"),
    (["южная америка", "conmebol", "судамерикана"], "Копа Судамерикана"),
    (["африка", "caf champions"],  "КАФ ЛЧ"),
    (["азия", "afc champions"],    "АФК ЛЧ"),
]

# Підрядки в назві ліги (raw_bracket) які означають НЕ футбол — матч відкидається
NON_FOOTBALL = [
    # ── Явні види спорту ──────────────────────────────────────────────────────
    "баскетбол", "хоккей", "теннис", "волейбол", "бокс", "гандбол", "бейсбол",
    "регби", "дартс", "снукер", "крикет", "гольф", "атлетика", "плавание",
    "борьба", "фехтование", "биатлон", "американский футбол",
    "бадминтон", "тхэквондо", "петанк", "нетбол", "флорбол",
    "пляжный волейбол", "пляжний волейбол",
    "мотоспорт", "автоспорт", "кёрлинг", "лыжи", "прыжки", "конькобежн",
    "велоспорт", "триатлон", "пятиборье", "парусный", "гребля", "стрельба",
    "ралли", "formula", "формула", "nascar", "racing", "мото",

    # ── Міжнародні баскетбольні турніри ──────────────────────────────────────
    "нба", "nba",
    "фиба", "fiba",
    "евролига", "euroleague",
    "еврокубок", "eurocup",
    "кубок европы фиба",
    "есбл",
    "адриатическая лига",
    "латвийско-эстонская лига",
    "единая лига втб", "лига втб", "втб",
    "женщины. балтийская лига",

    # ── Національні баскетбольні ліги ────────────────────────────────────────
    # Фінляндія
    "корислига", "korisliiga",
    # Словаччина (хокейна Екстраліга)
    "словакия. экстралига",
    # Болгарія
    "болгария. нбл",
    # Хорватія (баскетбол)
    "хорватия. премьер-лига",
    "хорватия. первая лига",
    "хорватия. женщины",
    # Чехія
    "чехия. нбл",
    "чехия. женщины. жбл",
    # Польща
    "польша. плк",
    # Румунія
    "румыния. национальная лига",
    # Греція
    "греция. гбл",
    "греция. а2 этники",
    "греция. женщины",
    # Литва
    "литва. лкл",
    "литва. нкл",
    # Латвія
    "латвия. нбл",
    # Туреччина (баскетбол — "Турция. Суперлига"; футбол ловимо тільки по "süper lig")
    "турция. суперлига",
    "турция. тбл",
    "турция. женщины. ткбл",
    "турция. женщины. кбсл",
    # Іспанія
    "испания. абк лига",
    "испания. примера феб",
    "liga endesa", "acb",
    # Франція
    "франция. нбл про а",
    "франция. нбл про б",
    # Німеччина (баскетбольна Бундесліга — відрізняємо від футбольної)
    "германия. бундеслига",   # на livetv баскетбол йде як "Германия. Бундеслига"
    # Італія
    "италия. лега баскет",
    "италия. серия а2",
    # Бразилія
    "бразилия. нбб",
    "бразилия. женщины. лбф",
    # Австралія
    "австралия. нбл",
    # Австрія
    "австрия. суперлига",
    # Північна Македонія
    "северная македония",
    # Словенія
    "словения. женщины",
    # Швейцарія
    "швейцария. женщины",
    # Ізраїль
    "израиль. суперлига",
    # Казахстан
    "казахстан. национальная лига",
    "казахстан. женщины",
    # Кіпр (баскетбол — є й футбольний Кіпр, тому точний рядок)
    "кипр. 1-й дивизион",
    # Росія
    "россия. суперлига",
    "россия. женщины. премьер-лига",
    # Тайвань
    "тайвань. сбл",
    "тайвань. тпбл",
    "тайвань. женщины",
    # Китай
    "китай. кба",
    # Філіппіни
    "филиппины.",
    # Загальні ключові слова
    "баскет",
    "wnba",
    "nbl",   # National Basketball League
    "нбл",   # те саме кирилицею (Болгарія, Чехія)

    # ── Волейбольні ліги ──────────────────────────────────────────────────────
    # Міжнародні
    "лига чемпионов женщины", "женщины. лига чемпионов",
    "среднеевропейская лига",
    # Серія А — волейбольна (відрізняємо від футбольної по наявності "серия а2"/"серия а3")
    "италия. серия а2", "италия. серия а3", "италия. серия а1",
    # Польща
    "польша. плюс-лига", "плюс-лига",
    "польша. женщины. мп",
    # Бразилія
    "бразилия. суперлига", "бразилия. женщины. суперлига",
    # Туреччина (волейбол)
    "эфелер лига", "турция. эфелер",
    "турция. женщины. эфелер", "турция. женщины. суперлига",
    # Іспанія (волейбол)
    "испания. суперлига", "испания. женщины. суперлига",
    # Росія (волейбол — окремо від суперліги баскет)
    "россия. суперлига волейбол",
    # Сербія (волейбол)
    "сербия. суперлига",
    # Чехія (волейбол)
    "чехия. экстралига",
    # Загальні волейбольні ключові слова
    "суперлига",    # ловить більшість нефутбольних суперліг (баскет + волейбол)
]

# Завжди показуємо (незалежно від gooool)
PRIORITY_LEAGUES = {
    "Лига чемпионов","АПЛ","Ла Лига","Серия А","Бундеслига","Лига 1 Франция",
    "Лига Европы","Лига конференций","УПЛ","Чемпионшип","МЛС","Кубок Англии",
    "Юнош. лига УЕФА","Кубок Украины","Лига наций","Эредивизи",
    "Примейра","Жюпилер","Суперлига Тур","Шотландия Пр","Саудовская Пр",
    "США. Открытый кубок","США. USL","КОНКАКАФ","Примера Арг",
    "Серия А Бр","Кубок Бразилии","Аргентина. Проф лига",
}

# Ліги де завжди показуємо якщо є Україна в назві команди
UKR_KW = ["україна","украина","збірна","сборная"]

# Ключові слова українських команд для бусту
UKR_TEAM_KW = [
    "динамо київ", "динамо киев", "шахтар", "шахтер",
    "україна", "украина", "збірна", "сборная",
    "металіст", "металист", "дніпро", "днепр",
    "ворскла", "зоря", "заря", "олімпік", "рух львів",
]

# Глобальні турніри де підвищуємо рейтинг українських команд
UKR_BOOST_LEAGUES = {
    "Лига чемпионов", "Лига Европы", "Лига конференций",
    "Лига наций", "Евро квал.", "ЧМ квал.",
    "Юнош. лига УЕФА", "Копа Либертадорес", "КОНКАКАФ",
}

def map_league(raw_bracket: str) -> str:
    """
    raw_bracket — текст з дужок: "Италия. Серия А" або "Лига Чемпионов"
    Повертає стандартизовану назву ліги.
    """
    lo = raw_bracket.lower().strip()
    for kws, name in LEAGUE_MAP:
        if any(k in lo for k in kws):
            return name
    # Якщо не знайдено — повертаємо сирий текст (без "Футбол.")
    clean = re.sub(r'^(футбол|football)[.\s]*', '', raw_bracket, flags=re.I).strip()
    return clean if clean else "Інше"

def is_football(text: str) -> bool:
    lo = text.lower()
    if any(s in lo for s in NON_FOOTBALL): return False
    return True

# ─── ІКОНКИ ЛІГИ (прапори flagcdn) ──────────────────────────────────────────
FLAG_MAP = {
    "Лига чемпионов": "ucl",
    "Лига Европы": "uel", "Лига конференций": "uecl",
    "АПЛ": "gb-eng", "Чемпионшип": "gb-eng", "Кубок Англии": "gb-eng",
    "Лига 1 Англия": "gb-eng", "Лига 2 Англия": "gb-eng",
    "Ла Лига": "es", "Сегунда": "es", "Кубок Испании": "es",
    "Бундеслига": "de", "2. Бундеслига": "de", "Кубок Германии": "de",
    "Серия А": "it", "Серия Б": "it", "Кубок Италии": "it",
    "Лига 1 Франция": "fr", "Лига 2 Франция": "fr", "Кубок Франции": "fr",
    "УПЛ": "ua", "Кубок Украины": "ua", "Первая лига Укр": "ua",
    "Эредивизи": "nl", "Кередивизи": "nl",
    "Примейра": "pt", "Жюпилер": "be",
    "Суперлига Тур": "tr", "Шотландия Пр": "gb-sct",
    "МЛС": "us", "США. Открытый кубок": "us", "США. USL": "us", "США. Женщины": "us",
    "Саудовская Пр": "sa",
    "Примера Арг": "ar", "Аргентина. Проф лига": "ar", "Аргентина": "ar",
    "Серия А Бр": "br", "Кубок Бразилии": "br", "Серия Б Бр": "br",
    "Серия В Бр": "br", "Серия Г Бр": "br", "Бразилия. Другое": "br",
    "РПЛ": "ru",
    "Суперлига Гр": "gr", "ХНЛ": "hr", "Экстракласа": "pl",
    "Бундеслига Авс": "at", "Фортуна Лига": "cz",
    "Суперлига Дан": "dk", "Алсвенскан": "se", "Элитесерен": "no",
    "Суперлига Шв": "ch", "Суперлига Рум": "ro",
    "Премьерлига Изр": "il", "Лига звёзд Кат": "qa",
    "Лига наций": "eu", "Евро квал.": "eu", "ЧМ квал.": "eu",
    "Юнош. лига УЕФА": "eu",
    "Колумбия": "co", "Чили": "cl", "Мексика": "mx", "Перу": "pe",
    "Боливия": "bo", "Эквадор": "ec", "Уругвай": "uy", "Венесуэла": "ve",
    "Парагвай": "py", "КОНКАКАФ": "mx", "Копа Либертадорес": "ar",
    "Копа Судамерикана": "ar",
    "Япония": "jp", "Китай": "cn", "Корея": "kr",
    "Австралия": "au", "Иран": "ir", "Индия": "in",
    "Египет": "eg", "Марокко": "ma", "Нигерия": "ng", "Гана": "gh",
    "Финляндия": "fi", "Ирландия": "ie", "Сербия": "rs",
    "Словакия": "sk", "Словения": "si", "Болгария": "bg",
    "Венгрия": "hu", "Босния": "ba", "Казахстан": "kz",
    "Беларусь": "by", "Литва": "lt", "Латвия": "lv", "Эстония": "ee",
    "Кипр": "cy", "Мальта": "mt", "Люксембург": "lu",
    "Сев. Ирландия": "gb-nir", "Уэльс": "gb-wls",
    "Исландия": "is", "Фарерские": "fo",
    "Азербайджан": "az", "Грузия": "ge", "Армения": "am",
    "Таиланд": "th", "Вьетнам": "vn", "Индонезия": "id",
    "Малайзия": "my", "Филиппины": "ph", "ЮАР": "za",
    "КАФ ЛЧ": "ng", "АФК ЛЧ": "jp",
}

UCL_SVG = ('<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg"'
           ' style="width:13px;height:13px;vertical-align:middle">'
           '<circle cx="7" cy="7" r="6.5" fill="#001489" stroke="#c8a400" stroke-width=".8"/>'
           '<polygon points="7,1.2 8.3,5.2 12.5,5.2 9.2,7.7 10.4,11.7 7,9.2 3.6,11.7 4.8,7.7 1.5,5.2 5.7,5.2"'
           ' fill="#c8a400"/></svg>')

UEL_SVG = ('<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg"'
           ' style="width:13px;height:13px;vertical-align:middle">'
           '<circle cx="7" cy="7" r="6.5" fill="#f26522" stroke="#fff" stroke-width=".5"/>'
           '<text x="7" y="9.5" text-anchor="middle" font-size="6" font-weight="bold" fill="white">UE</text>'
           '</svg>')

UECL_SVG = ('<svg viewBox="0 0 14 14" xmlns="http://www.w3.org/2000/svg"'
            ' style="width:13px;height:13px;vertical-align:middle">'
            '<circle cx="7" cy="7" r="6.5" fill="#00a651" stroke="#fff" stroke-width=".5"/>'
            '<text x="7" y="9.5" text-anchor="middle" font-size="5.5" font-weight="bold" fill="white">CL</text>'
            '</svg>')

def league_badge_html(name: str) -> str:
    code = FLAG_MAP.get(name, "")
    if code == "ucl":  return f'<span class="lg-ico">{UCL_SVG}</span>'
    if code == "uel":  return f'<span class="lg-ico">{UEL_SVG}</span>'
    if code == "uecl": return f'<span class="lg-ico">{UECL_SVG}</span>'
    if code:
        return f'<img class="lg-flag" src="https://flagcdn.com/16x12/{code}.png" alt="">'
    return ''

def fix_url(src: str) -> str | None:
    if not src: return None
    src = src.strip()
    if src.startswith("//"): return "https:" + src
    if src.startswith("/"): return "https://livetv.sx" + src
    if src.startswith("http"): return src
    return None

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
    BG = "background:#eef2fa;background-image:radial-gradient(ellipse 70% 40% at 50% -20%,rgba(30,100,220,0.1),transparent);"

CLR  = "#dde6f5" if DARK else "#1a2540"
CLRS = "#6b8ab0" if DARK else "#4a6080"
CARD = "rgba(10,20,50,0.72)" if DARK else "rgba(255,255,255,0.9)"
SB   = "rgba(6,12,30,0.97)" if DARK else "rgba(230,235,250,0.98)"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Pacifico&display=swap');
*{{box-sizing:border-box}}
html,body,[class*="css"]{{font-family:'Inter',sans-serif}}
.stApp{{{BG}min-height:100vh}}
#MainMenu,footer,header{{visibility:hidden}}
.block-container{{padding-top:0!important;max-width:1500px!important;position:relative!important;}}

.site-title{{
  font-family:'Pacifico',cursive;font-size:2.2em;font-weight:400;letter-spacing:.5px;
  display:block;
  background:linear-gradient(110deg,#a0650a 0%,#ffd234 25%,#ffe680 50%,#c8860a 75%,#ffd234 100%);
  background-size:300% auto;
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  animation:ts 3.5s linear infinite;
  line-height:1.2;padding:4px 0;
}}
@keyframes ts{{0%{{background-position:0%}}100%{{background-position:300%}}}}

/* ── Главный хедер ── */
.main-hdr{{
  display:flex;align-items:center;justify-content:space-between;
  padding:20px 0 16px;gap:12px;
}}
.main-hdr-right{{
  display:flex;align-items:center;gap:10px;flex-shrink:0;
}}
.hdr-update{{
  display:flex;align-items:center;gap:6px;
  font-size:.78em;font-weight:600;color:{CLRS};
  background:rgba(79,163,255,0.07);
  padding:5px 12px;border-radius:20px;
  border:1px solid rgba(79,163,255,0.15);
  white-space:nowrap;
}}
.hdr-update svg{{opacity:.55;flex-shrink:0;}}
/* ── Кнопка настроек в хедере ── */

.clock{{font-size:.84em;font-weight:600;color:{CLRS};background:rgba(79,163,255,0.08);
  padding:5px 14px;border-radius:20px;border:1px solid rgba(79,163,255,0.18);
  text-align:right;line-height:1.6;margin-top:14px}}
.clock b{{color:#4fa3ff}}

.matches-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(288px,1fr));gap:10px;padding-bottom:16px}}
.top-matches-wrapper{{display:flex;flex-direction:column;gap:10px;padding-bottom:16px}}
.top-row{{display:grid;gap:10px}}
.top-row.cols1{{grid-template-columns:1fr}}
.top-row.cols2{{grid-template-columns:1fr 1fr}}
.top-row.cols3{{grid-template-columns:1fr 1fr 1fr}}
.top-row.cols4{{grid-template-columns:1fr 1fr 1fr 1fr}}
/* Висота карток залежить від розміру рядка */
.top-row.h3 .mc{{min-height:400px}}
.top-row.h2 .mc{{min-height:260px}}
.top-row.h1 .mc{{min-height:160px}}

/* ── базова картка ── */
.mc{{
  background:{CARD};border:1px solid rgba(79,163,255,0.13);
  border-radius:14px;padding:12px 14px 10px;
  position:relative;overflow:hidden;
  transition:transform .15s,border-color .15s,box-shadow .15s;
  display:flex;flex-direction:column;
}}
.mc::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,#1a6fff,#00c6ff);opacity:.55}}
.mc:hover{{transform:translateY(-2px);border-color:rgba(79,163,255,0.38);
  box-shadow:0 4px 22px rgba(0,60,180,0.14)}}

/* ── live — НЕ фарбуємо фон червоним, тільки бейдж показує статус ── */
.mc.live{{border-color:rgba(79,163,255,0.2)!important}}
.mc.live::before{{background:linear-gradient(90deg,#1a6fff,#00c6ff);opacity:.6}}

/* ── топ (золота) ── */
.mc.top{{border-color:rgba(255,190,0,0.5)!important;
  background:linear-gradient(145deg,rgba(90,58,0,0.3),rgba(255,195,50,0.05))!important}}
.mc.top::before{{background:linear-gradient(90deg,#5a3a00,#ffd234,#5a3a00);
  background-size:200% 100%;opacity:1;animation:gs 3s linear infinite}}
@keyframes gs{{0%{{background-position:200% 0}}100%{{background-position:-200% 0}}}}

/* ── топ + live — золота картка з пульсуючим бейджем ── */
.mc.top.live{{border-color:rgba(255,190,0,0.6)!important;
  background:linear-gradient(145deg,rgba(90,58,0,0.35),rgba(255,195,50,0.07))!important}}

/* ── featured (пропорційні розміри у top-секції) ── */
.mc.feat .tlogo{{width:60px;height:60px}}
.mc.feat .tlogo img{{width:54px;height:54px}}
.mc.feat .tph{{width:54px;height:54px;font-size:1.5em}}
.mc.feat .tname{{font-size:.78em;max-width:130px}}

/* h3 рядок — великі елементи (1.25× більші) */
.top-row.h3 .mc.feat .tlogo{{width:120px;height:120px}}
.top-row.h3 .mc.feat .tlogo img{{width:108px;height:108px}}
.top-row.h3 .mc.feat .tph{{width:108px;height:108px;font-size:2.6em}}
.top-row.h3 .mc.feat .tname{{font-size:1.15em;max-width:240px}}
.top-row.h3 .mc.feat .mc-league{{font-size:.8em}}
.top-row.h3 .mc.feat .mc-time{{font-size:.95em}}
.top-row.h3 .mc.feat .sc-live{{font-size:2.4em}}
.top-row.h3 .mc.feat .sc-fin{{font-size:2.0em}}
.top-row.h3 .mc.feat .vs{{font-size:.95em}}
.top-row.h3 .mc.feat .star{{font-size:1.15em}}
.top-row.h3 .mc.feat .wbtn{{font-size:.78em}}

/* h2 рядок — середні елементи */
.top-row.h2 .mc.feat .tlogo{{width:74px;height:74px}}
.top-row.h2 .mc.feat .tlogo img{{width:66px;height:66px}}
.top-row.h2 .mc.feat .tph{{width:66px;height:66px;font-size:1.75em}}
.top-row.h2 .mc.feat .tname{{font-size:.86em;max-width:160px}}
.top-row.h2 .mc.feat .mc-league{{font-size:.65em}}
.top-row.h2 .mc.feat .mc-time{{font-size:.76em}}
.top-row.h2 .mc.feat .sc-live{{font-size:1.55em}}
.top-row.h2 .mc.feat .sc-fin{{font-size:1.3em}}
.top-row.h2 .mc.feat .star{{font-size:.85em}}

/* ── top-секція ── */
.top-wrap{{
  background:linear-gradient(160deg,rgba(90,58,0,0.22),rgba(140,90,0,0.07) 50%,rgba(60,35,0,0.18));
  border:1px solid rgba(255,190,0,0.17);border-radius:18px;
  padding:15px 17px 17px;margin-bottom:18px;position:relative;overflow:hidden
}}
.top-wrap::before{{content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 70% 50% at 50% -10%,rgba(255,185,0,0.09),transparent);
  pointer-events:none}}
.top-hdr{{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:13px}}
.top-hdr-txt{{font-size:.79em;font-weight:900;color:#ffd234;text-transform:uppercase;
  letter-spacing:2.5px;text-shadow:0 0 18px rgba(255,185,0,.5)}}
.top-hdr-s{{font-size:1em;color:#ffd234;animation:sp 2s ease-in-out infinite}}
@keyframes sp{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.45;transform:scale(.78)}}}}

/* ── шапка картки ── */
.mc-head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:9px;gap:4px}}
.mc-league{{display:inline-flex;align-items:center;gap:5px;font-size:.6em;font-weight:700;
  color:#4fa3ff;text-transform:uppercase;letter-spacing:.5px;
  background:rgba(79,163,255,0.1);padding:2px 8px 2px 5px;border-radius:20px;
  white-space:nowrap;flex-shrink:1;min-width:0;overflow:visible}}
.mc-league .lg-ico{{display:inline-flex;align-items:center;flex-shrink:0}}
.mc-league img.lg-flag{{width:16px;height:11px;border-radius:2px;object-fit:cover;flex-shrink:0}}
.mc-time{{font-size:.7em;font-weight:700;color:{CLRS};flex-shrink:0;white-space:nowrap}}
.mc-date{{font-size:.65em;font-weight:600;color:{CLRS};white-space:nowrap;letter-spacing:.2px}}

/* ── live badge ── */
.lbadge{{display:inline-flex;align-items:center;gap:4px;font-size:.56em;font-weight:900;
  padding:2px 7px;border-radius:20px;letter-spacing:1px;text-transform:uppercase;
  background:linear-gradient(90deg,#b0001c,#ff2240);color:#fff;
  box-shadow:0 0 9px rgba(190,0,35,.5);animation:lg 1.8s ease-in-out infinite;margin-right:3px}}
.lbadge .dot{{width:5px;height:5px;border-radius:50%;background:#fff;animation:lp 1.1s ease-in-out infinite}}
@keyframes lp{{0%,100%{{transform:scale(1);opacity:1}}50%{{transform:scale(1.9);opacity:.2}}}}
@keyframes lg{{0%,100%{{box-shadow:0 0 7px rgba(190,0,35,.45)}}50%{{box-shadow:0 0 15px rgba(255,35,55,.9)}}}}

/* ── команди ── */
.teams{{display:flex;align-items:center;justify-content:space-between;gap:6px;margin:3px 0 6px;flex:1}}
.team{{display:flex;flex-direction:column;align-items:center;flex:1;min-width:0}}
.tlogo{{width:48px;height:48px;display:flex;align-items:center;justify-content:center;margin-bottom:5px}}
.tlogo img{{width:44px;height:44px;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,.65))}}
.tph{{width:44px;height:44px;border-radius:10px;background:rgba(79,163,255,0.07);
  border:1.5px dashed rgba(79,163,255,0.17);display:flex;align-items:center;
  justify-content:center;font-size:1.2em;opacity:.4}}
.tname{{font-size:.72em;font-weight:600;color:{CLR};text-align:center;
  line-height:1.25;word-break:break-word;max-width:115px}}
.vs-b{{display:flex;flex-direction:column;align-items:center;gap:4px;flex-shrink:0}}
.vs{{font-size:.58em;font-weight:800;color:rgba(79,163,255,0.22);letter-spacing:1px}}
.sc-live{{font-size:1.28em;font-weight:900;color:#ff4455;letter-spacing:3px;
  animation:pulse-score 1.2s ease-in-out infinite}}
@keyframes pulse-score{{
  0%,100%{{color:#ff4455;text-shadow:0 0 8px rgba(255,68,85,.5)}}
  50%{{color:#ff8090;text-shadow:0 0 18px rgba(255,80,100,.9)}}
}}
.live-badge{{font-size:.52em;font-weight:800;letter-spacing:2px;
  color:#fff;background:linear-gradient(90deg,#c8001a,#ff3355);
  padding:1px 7px;border-radius:3px;
  animation:pulse-badge 1.4s ease-in-out infinite}}
@keyframes pulse-badge{{
  0%,100%{{opacity:1;box-shadow:0 0 6px rgba(255,50,80,.5)}}
  50%{{opacity:.75;box-shadow:0 0 14px rgba(255,50,80,.9)}}
}}
.btn-ltv{{color:#4fa3ff}}
.btn-go{{color:#00c97a}}
.btn-ai-footer{{color:#7c9cbf!important;font-weight:700;letter-spacing:.3px;text-decoration:none!important;}}
.sc-fin{{font-size:1.1em;font-weight:800;color:{CLRS};letter-spacing:2px}}
.star-row{{display:inline-flex;gap:1px;align-items:center;vertical-align:middle}}
.star{{font-size:.72em;line-height:1}}
.star.filled{{color:#ffd234;filter:drop-shadow(0 0 3px rgba(255,210,52,.7))}}
.star.blue{{color:#4fa3ff;filter:drop-shadow(0 0 3px rgba(79,163,255,.6))}}

/* ── footer зірки — просте відображення без інтерактивності ── */
.footer-stars{{display:inline-flex;align-items:center;gap:1px;padding:2px 4px;border:none}}
.footer-stars-blue{{border:none!important}}
/* ── кнопки ── */
.mc-foot{{margin-top:auto;padding-top:8px;border-top:1px solid rgba(79,163,255,0.07);
  display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap}}
.watch-label{{font-size:.58em;font-weight:600;color:{CLRS};letter-spacing:.3px;white-space:nowrap}}
.mc-btns{{display:flex;gap:6px;flex-wrap:wrap;align-items:center}}
.mc-tv-ico{{font-size:.9em;opacity:.6;flex-shrink:0;line-height:1}}
.wbtn{{display:inline-flex;align-items:center;
  font-size:.68em;font-weight:600;padding:0;border:none;border-radius:0;
  text-decoration:underline;text-underline-offset:2px;
  letter-spacing:.2px;transition:opacity .15s;white-space:nowrap;background:none}}
.wbtn:hover{{opacity:.65}}
.btn-ltv{{color:#4fa3ff}}
.btn-go{{color:#00c97a}}



/* ── топ картки: яскравість ободку за кількістю зірок ── */
.mc.top.stars1{{border-color:rgba(255,190,0,0.12)!important;box-shadow:none!important}}
.mc.top.stars2{{border-color:rgba(255,190,0,0.25)!important;box-shadow:none!important}}
.mc.top.stars3{{border-color:rgba(255,190,0,0.42)!important;box-shadow:0 0 8px rgba(255,185,0,0.07)!important}}
.mc.top.stars4{{border-color:rgba(255,190,0,0.62)!important;box-shadow:0 0 12px rgba(255,185,0,0.14)!important}}
.mc.top.stars5{{border-color:rgba(255,210,52,0.90)!important;box-shadow:0 0 20px rgba(255,185,0,0.28)!important}}

div[data-testid="stTabs"] button{{font-size:.75em!important;font-weight:600!important;color:{CLRS}!important}}
div[data-testid="stTabs"] button[aria-selected="true"]{{color:#4fa3ff!important}}

/* ── Скриваємо sidebar повністю ── */
section[data-testid="stSidebar"],
[data-testid="collapsedControl"]{{display:none!important}}

.stCheckbox label span{{font-size:.82em!important}}

/* ── Хедер ── */
.hdr{{display:flex;align-items:center;justify-content:space-between;padding:12px 0 4px;gap:12px}}
.hdr-right{{display:flex;align-items:center;gap:10px;flex-shrink:0}}
.hdr-clock{{font-size:.84em;font-weight:600;color:{CLRS};background:rgba(79,163,255,0.08);
  padding:5px 14px;border-radius:20px;border:1px solid rgba(79,163,255,0.18);
  text-align:right;line-height:1.5}}
.hdr-clock b{{color:#4fa3ff}}
/* Dialog / Modal overrides */
[data-testid="stDialog"] > div > div{{
  background:rgba(8,15,36,0.97)!important;
  border:1px solid rgba(79,163,255,0.18)!important;
  border-radius:18px!important;
  box-shadow:0 8px 60px rgba(0,20,80,0.7)!important;
  max-width:860px!important;width:90vw!important;
}}
[data-testid="stDialog"] h3{{color:#dde6f5!important;font-size:1.1em!important}}

</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=90)
def load_livetv_live():
    """Завантажує ТІЛЬКИ live-матчі з livetv.sx/alllivesports/ — оновлення кожні 90 сек"""
    ck = f"ltv_live_{TZ}"
    cached = cache_get(ck, ttl=90)
    if cached: return cached

    live_ids: set = set()
    live_scores: dict = {}
    try:
        # /alllivesports/ — тільки live матчі (не upcoming)
        r = requests.get("https://livetv.sx/alllivesports/",
                         timeout=20, headers=HDR, verify=False)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Структура: <img src="live.gif"><span class="live"> &nbsp; 2:2 </span>
        # Шукаємо live.gif → беремо наступний span.live → витягуємо event_id з батьківського блоку
        for img in soup.find_all("img", src=re.compile(r"live\.gif", re.I)):
            # Рахунок: наступний span.live одразу після img
            nxt = img.find_next_sibling("span", class_="live")
            if not nxt:
                parent = img.parent
                nxt = parent.find("span", class_="live") if parent else None
            if not nxt: continue
            txt = nxt.get_text(strip=True)
            mm = re.search(r"^(\d{1,3}):(\d{1,3})$", txt)

            # Event ID: шукаємо посилання в тому ж блоці
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


@st.cache_data(ttl=600)
def load_livetv():
    ck = f"ltv10_{TZ}"
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

    # ── Знаходимо правий футбольний блок ─────────────────────────────────────
    # Структура: span.sltitle="Футбол" → td[valign=top] → таблиці:
    #   - Заголовок (width=100%, без matчів)
    #   - "Главные матчи дня" (cellpadding=3, якщо є)
    #   - Повний розклад (найбільша таблиця з матчами)
    top_table = None       # "Главные матчи дня"
    schedule_table = None  # Повний розклад по датах
    football_scope = soup  # fallback

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
                if not ct2: continue  # пропускаємо таблиці без матчів
                # "Главные матчи дня": має cellpadding=3 і bgcolor="#fffcec"
                has_top_bg = bool(t.find("td", attrs={"bgcolor": "#fffcec"}))
                if has_top_bg and top_table is None:
                    top_table = t
                # Розклад: найбільша таблиця з матчами (без bgcolor топу)
                elif not has_top_bg:
                    if schedule_table is None or len(str(t)) > len(str(schedule_table)):
                        schedule_table = t

            print(f"  top_table: {len(str(top_table)) if top_table else 0} байт "
                  f"({len(top_table.find_all('td', colspan='2')) if top_table else 0} матчів), "
                  f"schedule_table: {len(str(schedule_table)) if schedule_table else 0} байт "
                  f"({len(schedule_table.find_all('td', colspan='2')) if schedule_table else 0} матчів)",
                  flush=True)

    # ── Крок 1: Збираємо event_meta — тільки з top_table + schedule_table ────
    meta_scope = soup  # fallback
    if top_table or schedule_table:
        from bs4 import BeautifulSoup as BS4
        combined_html = ""
        if top_table: combined_html += str(top_table)
        if schedule_table: combined_html += str(schedule_table)
        meta_scope = BS4(combined_html, "html.parser")

    event_meta: dict = {}

    for a_tag in meta_scope.find_all("a", href=re.compile(r"/eventinfo/\d+")):
        m = re.search(r"/eventinfo/(\d+)", a_tag["href"])
        if not m: continue
        eid = m.group(1)
        if eid in event_meta: continue

        # ── ФІЛЬТР ПО СПОРТУ: img alt в батьківському td colspan=2 ──
        # alt="Футбол. Лига Чемпионов" → футбол ✓
        # alt="Волейбол. Италия. Серия А" → не футбол ✗
        # alt="Лига Чемпионов" (без спорту, live блок) → теж перевіряємо
        td_colspan = a_tag.find_parent("td", attrs={"colspan": "2"})
        sport_img = td_colspan.find("img", alt=True) if td_colspan else None
        sport_alt = sport_img.get("alt", "") if sport_img else ""
        sport_alt_lo = sport_alt.lower()

        NON_SPORT_PREFIXES = ("волейбол", "баскетбол", "хоккей", "теннис", "бокс",
                              "регби", "гонки", "бейсбол", "гандбол", "гольф",
                              "крикет", "дартс", "снукер", "биатлон", "лыж",
                              "фигурн", "борьб", "дзюдо", "карате", "плаван")
        if any(sport_alt_lo.startswith(p) for p in NON_SPORT_PREFIXES):
            continue  # точно не футбол

        # Знаходимо evdesc
        parent = a_tag.parent
        evdesc = None
        for _ in range(7):
            if parent is None: break
            evdesc = parent.find("span", class_="evdesc")
            if evdesc: break
            parent = parent.parent
        if not evdesc: continue

        evtext = evdesc.get_text(" ", strip=True)

        # Ліга: якщо img alt починається з "Футбол." — беремо з alt
        # Якщо alt без префікса (live блок) — беремо з evdesc
        if sport_alt_lo.startswith("футбол"):
            league_raw = re.sub(r"^футбол[.\s]*", "", sport_alt, flags=re.I).strip()
        else:
            lm = re.search(r"\(([^)]{2,90})\)\s*$", evtext)
            league_raw = lm.group(1).strip() if lm else ""
            # Додаткова перевірка для live блоку без "Футбол." prefix
            if not is_football(league_raw): continue
            nf_starts = ["баскетбол","хоккей","теннис","волейбол","бокс","регби",
                         "гонки","велос","плаван","атлет","борьб"]
            if any(league_raw.lower().startswith(s) for s in nf_starts): continue

        league = map_league(league_raw)

        # Логотип ліги з img src
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

    # ── Крок 2: Парсимо <td colspan="2"> ────────────────────────────────────
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

        # Парсинг дати/часу
        dt = None
        tm = re.search(r"(\d{1,2})\s+(\w+)\s+в\s+(\d{1,2}):(\d{2})", evtext)
        if tm:
            mon = MONTHS_RU.get(tm.group(2).lower())
            if mon:
                try:
                    # Зберігаємо як UTC (TZ_SITE), TZ конвертація — при читанні
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

        # Статус: спочатку перевіряємо наявність live.gif у рядку таблиці
        td_row = td.find_parent("tr") or td
        td_html = str(td_row)
        has_live_gif = "live.gif" in td_html or "liveicon" in td_html.lower()

        # Також шукаємо рахунок прямо в рядку (для live-матчів livetv показує його тут)
        inline_score = None
        if has_live_gif:
            for el in td_row.find_all(["td", "span", "div"]):
                if el.find("a"): continue
                txt = el.get_text(strip=True)
                mm = re.fullmatch(r"(\d{1,2})\s*[:\-]\s*(\d{1,2})", txt)
                if mm:
                    inline_score = f"{mm.group(1)}:{mm.group(2)}"
                    break

        # Статус по розкладу: якщо немає live.gif — використовуємо час
        delta = (datetime.now() - dt).total_seconds() / 60
        if has_live_gif:
            status = "live"
        elif 0 <= delta <= 115:
            status = "live"
        elif delta > 115:
            status = "finished"
        else:
            status = "upcoming"

        # Логотипи зі сторінки-списку
        t1_logo = t2_logo = None
        imgs = td.find_all("img", attrs={"itemprop": "image"})
        if len(imgs) >= 2:
            t1_logo = fix_url(imgs[0].get("src", ""))
            t2_logo = fix_url(imgs[1].get("src", ""))
        if not t1_logo or not t2_logo:
            for i, a2 in enumerate(td.find_all("a", href=re.compile(r"/clubinfo/\d+"))[:2]):
                img2 = a2.find("img")
                if img2:
                    src = fix_url(img2.get("src", ""))
                    if src:
                        if i == 0: t1_logo = t1_logo or src
                        else: t2_logo = t2_logo or src
        if not t1_logo or not t2_logo:
            for i, img2 in enumerate(
                td.find_all("img", src=re.compile(r"/clublogos/|/i/club|/logos/"))[:2]
            ):
                src = fix_url(img2.get("src", ""))
                if i == 0: t1_logo = t1_logo or src
                elif i == 1: t2_logo = t2_logo or src

        t1n, t2n = title, ""
        mp = re.match(r"^(.+?)\s*[–—]\s*(.+)$", title.strip())
        if mp: t1n, t2n = mp.group(1).strip(), mp.group(2).strip()

        league = meta["league"]
        league_raw = meta["league_raw"]

        # "Завжди показуємо" — популярні ліги + Укр команди
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

    # ── Топ-матчі: з top_table (Главные матчи дня) ───────────────────────────
    top_ids: set = set()
    # Шукаємо "Главные матчи" в top_table або в soup як fallback
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
        # Якщо "Главные матчи" не знайдено — парсимо всю top_table
        for td in top_table.find_all("td", colspan="2"):
            res = parse_td(td, is_top=True)
            if res:
                top_ids.add(res["event_id"])
                top_list.append(res)

    # ── Всі матчі: тільки з schedule_table ───────────────────────────────────
    # schedule_table = table[3] = тільки футбол, гарантовано без інших спортів
    all_search_scope = schedule_table if schedule_table else meta_scope
    for td in all_search_scope.find_all("td", colspan="2"):
        res = parse_td(td, is_top=False)
        if res and res["event_id"] not in top_ids:
            all_list.append(res)

    result = {"top": top_list, "all": all_list}
    cache_set(ck, result)
    print(f"livetv: top={len(top_list)}, all={len(all_list)}", flush=True)
    return result

# ─── РАХУНОК ЗІ СТОРІНКИ МАТЧУ ──────────────────────────────────────────────
def fetch_event_page(event_id: str, event_url: str, status: str) -> dict:
    """
    Не агресивно: кеш 5 хв для live, 24h для завершених.
    Повертає {"score": "1:0"|None, "t1": url|None, "t2": url|None}
    """
    # live: 90 сек, завершені: 48h, майбутні: 6h (тільки для логотипів)
    ttl = 90 if status == "live" else (172800 if status == "finished" else 21600)
    ck = f"ep2_{event_id}"
    cached = cache_get(ck, ttl=ttl)
    if cached: return cached

    result = {"score": None, "t1": None, "t2": None}
    try:
        r = requests.get(event_url, timeout=10, headers=HDR, verify=False)
        r.raise_for_status()
        s = BeautifulSoup(r.text, "html.parser")

        # Рахунок зі сторінки матчу livetv.sx
        # Структура: <td><a href="/eventinfo/ID/"><img src="live.gif"></a><span class="live">2:2</span></td>
        score = None

        # Шукаємо td що містить live.gif І посилання на цей конкретний матч
        for img in s.find_all("img", src=re.compile(r"live\.gif", re.I)):
            td = img.find_parent("td")
            if not td: continue
            # Перевіряємо: чи є в цьому td посилання на наш event_id
            a = td.find("a", href=re.compile(rf"/eventinfo/{event_id}"))
            if not a: continue
            # Беремо span.live з цього td
            span = td.find("span", class_="live")
            if not span: continue
            txt = span.get_text(strip=True)
            mm = re.search(r"^(\d{1,3}):(\d{1,3})$", txt)
            if mm:
                g1, g2 = int(mm.group(1)), int(mm.group(2))
                if g1 <= 30 and g2 <= 30:
                    score = f"{g1}:{g2}"
            break  # знайшли потрібний td — виходимо

        for sel in ["td.score", "span.score", ".lscore", ".mscore", ".score",
                    "[class*='score']", "td.lbc", "span.lbc", "[class*='result']"]:
            try:
                for el in s.select(sel):
                    txt = el.get_text(strip=True)
                    m2 = re.search(r"(\d{1,3})\s*[:\-]\s*(\d{1,3})", txt)
                    if m2:
                        h, mn = int(m2.group(1)), int(m2.group(2))
                        if h <= 30 and mn <= 30:  # футбольний рахунок
                            score = f"{h}:{mn}"; break
                if score: break
            except: pass

        # Варіант 2: у заголовку сторінки — формат "Team1 1:0 Team2"
        if score is None:
            title_tag = s.find("title")
            if title_tag:
                m2 = re.search(r"\b(\d{1,2})\s*[:\-]\s*(\d{1,2})\b", title_tag.get_text())
                if m2:
                    h, mn = int(m2.group(1)), int(m2.group(2))
                    if h <= 30 and mn <= 30:
                        score = f"{h}:{mn}"

        # Варіант 3: ізольований рядок = лише рахунок
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

        # Логотипи
        logos = []
        for img in s.find_all("img", attrs={"itemprop": "image"}):
            src = fix_url(img.get("src", ""))
            if src and src not in logos: logos.append(src)
        if len(logos) < 2:
            for img in s.find_all("img", src=re.compile(r"/clublogos/|/logos/|/i/club")):
                src = fix_url(img.get("src", ""))
                if src and src not in logos: logos.append(src)
        if logos: result["t1"] = logos[0]
        if len(logos) > 1: result["t2"] = logos[1]
    except Exception as e:
        print(f"  event {event_id}: {e}", flush=True)

    # Рахунок повертаємо ТІЛЬКИ для live або finished матчів
    if status == "upcoming":
        result["score"] = None
    cache_set(ck, result)
    return result
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
    """Тягне рахунок live-матчу зі сторінки gooool365"""
    if not gurl: return None
    ck = f"gscore_{hashlib.md5(gurl.encode()).hexdigest()[:10]}"
    cached = cache_get(ck, ttl=60)  # кеш 60 сек для live
    if cached is not None: return cached.get("score")
    try:
        r = requests.get(gurl, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        s = BeautifulSoup(r.text, "html.parser")
        # Шукаємо рахунок у різних місцях
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
        # Шукаємо у заголовку сторінки
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


_uri_cache: dict = {}

def get_uri(url: str) -> str | None:
    if not url: return None
    if url not in _uri_cache:
        _uri_cache[url] = logo_uri(url)
    return _uri_cache[url]

def lhtml(url: str) -> str:
    src = get_uri(url) if url else None
    if not src: src = url
    if src:
        return (f'<img src="{src}" loading="lazy" '
                f'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\'">'
                f'<div class="tph" style="display:none">⚽</div>')
    return '<div class="tph">⚽</div>'

def render_card(m: dict, gurl: str | None = None, feat: bool = False) -> str:
    t1, t2 = m["team1"], m["team2"]
    is_live = m["status"] == "live"
    is_fin  = m["status"] == "finished"
    league  = m["league"]
    MONTHS_UA_SHORT = ["","СІЧ","ЛЮТ","БЕР","КВІ","ТРА","ЧЕР","ЛИП","СЕР","ВЕР","ЖОВ","ЛИС","ГРУ"]
    tstr    = f'{m["time_dt"].day} {MONTHS_UA_SHORT[m["time_dt"].month]} {m["time_dt"].strftime("%H:%M")}'
    score   = m.get("score") if SHOW_SCORE else None
    interest = m.get("interest", 0)

    # CSS-класи картки
    if m.get("is_top"):
        stars_cls = f" stars{interest}" if interest > 0 else ""
        cls = f"mc top{stars_cls}"
    else:
        cls = "mc"
    if is_live: cls += " live"
    if feat: cls += " feat"

    badge_html = league_badge_html(league)

    # ltv_logo — тільки якщо немає нормального прапора/іконки у FLAG_MAP
    if not FLAG_MAP.get(league):
        ltv_logo = m.get("league_logo")
        if ltv_logo:
            badge_html = (f'<img src="{ltv_logo}" style="width:14px;height:14px;'
                          f'object-fit:contain;vertical-align:middle;margin-right:1px" '
                          f'onerror="this.style.display=\'none\'">')

    # Ліга-бейдж у шапці
    lg_html = (f'<div style="display:flex;align-items:center;gap:5px;flex-wrap:nowrap">'
               f'<div class="mc-league">{badge_html}{league}</div>'
               f'</div>')

    # Зірки у шапці
    if m.get("is_top") and interest > 0:
        stars_inner = "".join(f'<span class="star filled">★</span>' for _ in range(interest))
        head_stars = f'<span class="star-row" style="flex-shrink:0">{stars_inner}</span>'
    else:
        head_stars = '<span class="star-row" style="flex-shrink:0"><span class="star blue">★</span></span>'

    # Google AI ссылка
    match_date = m["time_dt"].strftime("%d.%m.%Y")
    ai_query = (
        f'{t1} vs {t2} {league} {match_date}: '
        f'составы и ключевые игроки, история личных встреч, '
        f'текущая форма команд, травмы и дисквалификации, '
        f'тактические особенности, прогноз и коэффициенты, '
        f'почему стоит посмотреть этот матч'
    )
    ai_url = 'https://www.google.com/search?q=' + urllib.parse.quote(ai_query) + '&udm=50'

    lc = " live" if is_live else ""
    btn_ltv = f'<a class="wbtn btn-ltv" href="{m["url"]}" target="_blank">Livetv</a>'
    btn_go  = f'<a class="wbtn btn-go" href="{gurl}" target="_blank">Gooool365</a>' if gurl else ""

    sep = '<span style="color:rgba(79,163,255,0.25);font-size:.65em">|</span>'
    links = f'{btn_go} {sep} {btn_ltv}' if gurl else btn_ltv
    watch_btns = links

    ai_prognoz = f'<a class="wbtn btn-ai-footer" href="{ai_url}" target="_blank">ПРОГНОЗ</a>'

    # Центр: LIVE + счёт/VS + ПРОГНОЗ
    if is_live:
        if score and SHOW_SCORE:
            center = (f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px;flex-shrink:0">'
                      f'<div class="vs-b">'
                      f'<div class="live-badge">LIVE</div>'
                      f'<div class="sc-live">{score}</div>'
                      f'</div>'
                      f'{ai_prognoz}'
                      f'</div>')
        else:
            center = (f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px;flex-shrink:0">'
                      f'<div class="vs-b"><div class="live-badge">LIVE</div></div>'
                      f'{ai_prognoz}'
                      f'</div>')
    elif is_fin and score and SHOW_SCORE:
        center = (f'<div class="vs-b">'
                  f'<div class="sc-fin">{score}</div>'
                  f'</div>')
    else:
        center = (f'<div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0">'
                  f'{ai_prognoz}'
                  f'</div>')

    footer = (f'<div class="mc-foot">'
              f'<span class="mc-date">{tstr}</span>'
              f'<div class="mc-btns">{watch_btns}</div>'
              f'</div>')

    return (f'<div class="{cls}">'
            f'<div class="mc-head" style="align-items:flex-start">{lg_html}'
            f'<div style="display:flex;align-items:center;gap:6px;flex-shrink:0">'
            f'{head_stars}</div></div>'
            f'<div class="teams">'
            f'<div class="team"><div class="tlogo">{lhtml(m.get("t1_logo"))}</div>'
            f'<div class="tname">{t1}</div></div>'
            f'{center}'
            f'<div class="team"><div class="tlogo">{lhtml(m.get("t2_logo"))}</div>'
            f'<div class="tname">{t2 or "?"}</div></div>'
            f'</div>'
            f'{footer}'
            f'</div>')

# ─── ЗАВАНТАЖЕННЯ ─────────────────────────────────────────────────────────────
pb = st.progress(0, text="Загрузка livetv.sx...")
ltv = load_livetv()
pb.progress(40, text="Live матчи...")
live_data = load_livetv_live()
live_ids_set = set(live_data.get("ids", []))
live_scores_map = live_data.get("scores", {})
pb.progress(55, text="gooool365...")
glist = load_gooool_urls()
pb.progress(85, text="Обработка...")
# now у часовому поясі користувача (для правильного визначення "сьогодні")
now = datetime.utcnow() + timedelta(hours=TZ)

seen_ids: set = set()
combined: list = []
for m in ltv["top"] + ltv["all"]:
    if m["event_id"] in seen_ids: continue
    seen_ids.add(m["event_id"])
    # Оновлюємо статус з live-сторінки — тільки якщо час матчу вже настав
    eid = m["event_id"]
    if eid in live_ids_set:
        try:
            match_dt = datetime.fromisoformat(m["time"])
            minutes_since = (datetime.now() - match_dt).total_seconds() / 60
            # Вважаємо live тільки якщо матч стартував (>= -2 хв) і не завершився (< 140 хв)
            if -2 <= minutes_since <= 140:
                m = dict(m)
                m["status"] = "live"
                if eid in live_scores_map:
                    m["score"] = live_scores_map[eid]
        except: pass
    combined.append(m)

# ── Знаходимо ВСІ ліги (для налаштувань) ────────────────────────────────────
LEAGUE_POP = {
    # ── Топ клубные UEFA ────────────────────────────────────────────
    'Лига чемпионов': 1, 'Лига Европы': 2, 'Лига конференций': 3,
    # ── Топ-5 лиг ───────────────────────────────────────────────────
    'АПЛ': 4, 'Ла Лига': 5, 'Бундеслига': 6, 'Серия А': 7, 'Лига 1 Франция': 8,
    # ── Кубки топ-5 ─────────────────────────────────────────────────
    'Кубок Англии': 9, 'Кубок Испании': 10, 'Кубок Италии': 11,
    'Кубок Франции': 12, 'Кубок Германии': 13,
    # ── Сборные — мировые турниры ────────────────────────────────────
    'Лига наций': 14, 'Евро квал.': 15, 'ЧМ квал.': 16,
    'Юнош. лига УЕФА': 17,
    'Копа Либертадорес': 18, 'Копа Судамерикана': 19, 'КОНКАКАФ': 20,
    'КАФ ЛЧ': 21, 'АФК ЛЧ': 22,
    # ── Другие топ-лиги ─────────────────────────────────────────────
    'Чемпионшип': 23, 'Эредивизи': 24, 'Примейра': 25, 'Жюпилер': 26,
    'Суперлига Тур': 27, 'Шотландия Пр': 28,
    'МЛС': 29, 'Саудовская Пр': 30,
    'Примера Арг': 31, 'Серия А Бр': 32,
    # ── УПЛ ─────────────────────────────────────────────────────────
    'УПЛ': 33, 'Кубок Украины': 34, 'Первая лига Укр': 35,
    # ── Вторые дивизионы ─────────────────────────────────────────────
    '2. Бундеслига': 36, 'Лига 2 Франция': 37, 'Сегунда': 38,
    'Серия Б': 39, 'Лига 1 Англия': 40, 'Лига 2 Англия': 41,
    # ── Другие ───────────────────────────────────────────────────────
    'Суперлига Гр': 42, 'ХНЛ': 43, 'Экстракласа': 44,
    'Бундеслига Авс': 45, 'Фортуна Лига': 46, 'РПЛ': 47,
    'Суперлига Дан': 48, 'Алсвенскан': 49, 'Элитесерен': 50,
    'Суперлига Шв': 51, 'Суперлига Рум': 52,
    'Премьерлига Изр': 53, 'Лига звёзд Кат': 54, 'Кередивизи': 55,
    'США. Открытый кубок': 56, 'США. USL': 57,
    'Кубок Бразилии': 58, 'Серия Б Бр': 59, 'Аргентина. Проф лига': 60,
}

def league_sort_key(lg):
    return (LEAGUE_POP.get(lg, 999), lg)

all_known_leagues_current = set(m["league"] for m in combined)  # ВСІ ліги до фільтру

# Підвантажуємо збережені ліги з попередніх сесій і об'єднуємо
_saved_leagues = load_known_leagues()
all_known_leagues_merged = all_known_leagues_current | _saved_leagues

# Сохраняем новые лиги в накопительный файл (не трогает настройки и кеш)
if all_known_leagues_current - _saved_leagues:
    save_known_leagues(all_known_leagues_merged)

all_known_leagues = sorted(all_known_leagues_merged, key=league_sort_key)

# ── Фільтр по вибраних лігах ────────────────────────────────────────────────
# ACTIVE_LGS == set() → показуємо всі (не налаштовано ще)
def league_allowed(lg: str) -> bool:
    if not ACTIVE_LGS: return True
    return lg in ACTIVE_LGS

matches: list = []
for gm in combined:
    try:
        dt = datetime.fromisoformat(gm["time"])
        # Конвертуємо з UTC сайту (TZ_SITE) в часовий пояс користувача (TZ)
        dt = dt + timedelta(hours=TZ - TZ_SITE)
    except: continue
    gurl = find_gooool(gm["team1"], gm["team2"], glist)
    # Рейтинг зацікавленості матчу (0..5)
    i_score = match_interest_score(gm["team1"], gm["team2"], gm.get("league","")) if SHOW_INTERESTING else 0
    interesting = i_score > 0
    is_top_final = gm.get("is_top") or interesting
    # Фільтр по лігах
    if not league_allowed(gm["league"]): continue
    # Якщо ліга явно вибрана юзером — показуємо ВСІ матчі з неї
    user_selected = bool(ACTIVE_LGS) and gm["league"] in ACTIVE_LGS
    if not gurl and not gm.get("always_show") and not is_top_final and not user_selected: continue
    matches.append({**gm, "time_dt": dt, "gooool_url": gurl,
                    "is_top": is_top_final, "interest": i_score})

matches.sort(key=lambda x: x["time_dt"])
# Гарантовано обнуляємо рахунок для майбутніх матчів
for m in matches:
    if m["status"] == "upcoming":
        m["score"] = None
pb.progress(100, text="Готово!")
pb.empty()

# ── Рахунок + логотипи зі сторінок матчів ────────────────────────────────────
# Логотипи тягнемо для всіх, рахунок — тільки live/finished
need_page = [m for m in matches if
    (SHOW_SCORE and m["status"] in ("live","finished") and not m.get("score")) or
    (not m.get("t1_logo") or not m.get("t2_logo"))]

if need_page:
    ev_bar = st.progress(0, text=f"Детали: 0/{min(len(need_page),50)}")
    for i, m in enumerate(need_page[:50]):
        data = fetch_event_page(m["event_id"], m["url"], m["status"])
        if SHOW_SCORE and m["status"] in ("live","finished") and not m.get("score") and data.get("score"):
            m["score"] = data["score"]
        # Если live и счёт всё ещё не получен — тянем с gooool
        if SHOW_SCORE and m["status"] == "live" and not m.get("score") and m.get("gooool_url"):
            gscore = fetch_score_from_gooool(m["gooool_url"])
            if gscore:
                m["score"] = gscore
        if not m.get("t1_logo") and data.get("t1"): m["t1_logo"] = data["t1"]
        if not m.get("t2_logo") and data.get("t2"): m["t2_logo"] = data["t2"]
        ev_bar.progress((i+1)/min(len(need_page),50),
                        text=f"Детали: {i+1}/{min(len(need_page),50)}")
    ev_bar.empty()

# ── Кеш логотипів на диск ────────────────────────────────────────────────────
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


@st.dialog("Настройки", width="large")
def settings_modal():
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
    # Індекс: UTC-5 = 0, UTC+0 = 5, UTC+2 = 7, UTC+3 = 8 ...
    TZ_BASE = -5  # мінімальне значення в списку
    tz_idx = max(0, min(TZ - TZ_BASE, len(TZ_OPTIONS) - 1))
    new_tz_label = st.selectbox("Мой часовой пояс", TZ_OPTIONS, index=tz_idx, key="m_tz")
    new_tz = TZ_OPTIONS.index(new_tz_label) + TZ_BASE

    new_score = st.checkbox("Показывать счёт", value=SHOW_SCORE, key="m_sc")
    new_interesting = st.checkbox(
        "Интересные команды — выносить матчи топ-100 клубов в «Главные матчи дня»",
        value=SHOW_INTERESTING, key="m_int"
    )
    new_boost_ukraine = st.checkbox(
        "Приоритет украинским командам в международных турнирах (ЛЧ, ЛЕ, сборные и т.д.)",
        value=BOOST_UKRAINE, key="m_ukr"
    )
    new_dark = DARK  # тема не змінюється через UI

    st.markdown("---")
    st.markdown("#### Лиги")
    st.caption("Отмеченные лиги отображаются. Если все сняты — показываются все.")

    if "lg_override" not in st.session_state:
        st.session_state.lg_override = None
    if "lg_override_gen" not in st.session_state:
        st.session_state.lg_override_gen = 0

    col_sel, col_clr, col_empty = st.columns([1, 1, 2])
    with col_sel:
        if st.button("Выбрать все", use_container_width=True, key="m_selall", type="primary"):
            st.session_state.lg_override = "all"
            st.session_state.lg_override_gen += 1
    with col_clr:
        if st.button("Снять все", use_container_width=True, key="m_clrall"):
            st.session_state.lg_override = "none"
            st.session_state.lg_override_gen += 1
    st.write("")

    # Визначаємо початкові значення чекбоксів
    if st.session_state.lg_override == "all":
        default_active = set(all_known_leagues)
    elif st.session_state.lg_override == "none":
        default_active = set()
    else:
        default_active = set(ACTIVE_LGS) if ACTIVE_LGS else set(all_known_leagues)

    gen = st.session_state.lg_override_gen
    new_active: set = set()
    cols_n = 4
    rows = [all_known_leagues[i:i+cols_n] for i in range(0, len(all_known_leagues), cols_n)]
    for row in rows:
        rcols = st.columns(cols_n)
        for col, lg in zip(rcols, row):
            with col:
                if st.checkbox(lg, value=(lg in default_active), key=f"m_lg_{lg}_{gen}"):
                    new_active.add(lg)

    st.write("")  # скидаємо колонковий контекст
    st.markdown("---")
    _c1, _c2, _c3 = st.columns(3)
    with _c1:
        if st.button("Сохранить", use_container_width=True, key="m_save", type="primary"):
            st.session_state.lg_override = None
            save_active = [] if new_active == set(all_known_leagues) else list(new_active)
            save_known_leagues(set(all_known_leagues))
            save_cfg({
                "tz_offset": new_tz,
                "show_score": new_score,
                "dark_theme": new_dark,
                "show_interesting": new_interesting,
                "boost_ukraine": new_boost_ukraine,
                "active_leagues": save_active,
            })
            st.cache_data.clear()
            for f in os.listdir(CACHE_DIR):
                fp = os.path.join(CACHE_DIR, f)
                if os.path.isfile(fp):
                    try: os.remove(fp)
                    except: pass
            st.rerun()
    with _c2:
        if st.button("Обновить данные", use_container_width=True, key="m_ref"):
            st.cache_data.clear()
            for f in os.listdir(CACHE_DIR):
                fp = os.path.join(CACHE_DIR, f)
                if os.path.isfile(fp):
                    try: os.remove(fp)
                    except: pass
            st.rerun()
    with _c3:
        if st.button("Сбросить кэш", use_container_width=True, key="m_cache"):
            st.cache_data.clear()
            for f in os.listdir(CACHE_DIR):
                fp = os.path.join(CACHE_DIR, f)
                if os.path.isfile(fp):
                    try: os.remove(fp)
                    except: pass
            st.rerun()
    st.caption(f"Сайт UTC+{TZ_SITE} → ваш UTC{new_tz:+d} · {len(all_known_leagues)} лиг · {len(matches)} матчей")


# ─── HEADER ──────────────────────────────────────────────────────────────────
now_str = now.strftime('%d.%m.%Y  %H:%M')

refresh_svg = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="23 4 23 10 17 10"/>'
    '<path d=\'M20.49 15a9 9 0 1 1-2.12-9.36L23 10\'/>'
    '</svg>'
)

_col_logo, _col_mid, _col_right = st.columns([3, 5, 1])
with _col_logo:
    st.markdown('<div class="site-title" style="padding:14px 0 10px">Sporter</div>', unsafe_allow_html=True)
with _col_mid:
    pass
with _col_right:
    st.markdown('<div style="padding-top:14px">', unsafe_allow_html=True)
    open_cfg = st.button("Настройки", key="open_cfg", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)
    if open_cfg:
        settings_modal()

# ─── ДАТИ ─────────────────────────────────────────────────────────────────────
today = now.date(); tomorrow = today + timedelta(days=1)
days_ua = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]

by_day: defaultdict = defaultdict(list)
for m in matches: by_day[m["time_dt"].date()].append(m)
sorted_days = sorted(by_day.keys())

if not sorted_days:
    st.warning("Матчей не найдено. Проверьте настройки лиг или обновите данные.")
    st.stop()

def build_top_section(day_matches_list):
    """Будує HTML блоку Головні матчі дня для заданого списку матчів"""
    top = sorted([m for m in day_matches_list if m.get("is_top")],
                 key=lambda x: (-x.get("interest", 0), x["time_dt"]))
    if not top: return ""
    hdr = ('<div class="top-hdr">'
           '<span class="top-hdr-s">✦</span>'
           '<span class="top-hdr-txt">Главные матчи дня</span>'
           '<span class="top-hdr-s">✦</span>'
           '</div>')
    rows = '<div class="top-matches-wrapper">'
    idx, n = 0, len(top)
    if idx < n:
        rows += '<div class="top-row cols1 h3">'
        rows += render_card(top[idx], top[idx].get("gooool_url"), feat=True)
        rows += '</div>'; idx += 1
    if idx < n:
        chunk = top[idx:idx+2]
        rows += f'<div class="top-row cols{len(chunk)} h2">'
        for cm in chunk: rows += render_card(cm, cm.get("gooool_url"), feat=True)
        rows += '</div>'; idx += len(chunk)
    if idx < n:
        chunk = top[idx:idx+3]
        rows += f'<div class="top-row cols{len(chunk)} h1">'
        for cm in chunk: rows += render_card(cm, cm.get("gooool_url"), feat=True)
        rows += '</div>'; idx += len(chunk)
    while idx < n:
        chunk = top[idx:idx+4]
        rows += f'<div class="top-row cols{min(len(chunk),4)} h1">'
        for cm in chunk: rows += render_card(cm, cm.get("gooool_url"), feat=True)
        rows += '</div>'; idx += len(chunk)
    rows += '</div>'
    return hdr + rows

# ── Таби дат → топ-матчі → таби ліг ─────────────────────────────────────────
def dlabel(d):
    if d == today:    return f"Сегодня {d.strftime('%d.%m')}"
    if d == tomorrow: return f"Завтра {d.strftime('%d.%m')}"
    return f"{days_ua[d.weekday()]} {d.strftime('%d.%m')}"

day_tabs = st.tabs([dlabel(d) for d in sorted_days])

for day_tab, day in zip(day_tabs, sorted_days):
    with day_tab:
        day_matches = by_day[day]

        # Топ-матчі дня
        top_html = build_top_section(day_matches)
        if top_html:
            st.markdown(top_html, unsafe_allow_html=True)

        # Таби ліг
        leagues_day = sorted(set(m["league"] for m in day_matches), key=league_sort_key)
        tab_labels = ["Все"] + leagues_day
        league_tabs = st.tabs(tab_labels)

        for lt, lbl in zip(league_tabs, tab_labels):
            with lt:
                fl = day_matches if lbl == "Все" else [m for m in day_matches if m["league"] == lbl]
                if not fl:
                    st.caption("Матчей нет")
                    continue
                grid = '<div class="matches-grid">'
                for m in fl:
                    grid += render_card(m, m.get("gooool_url"))
                grid += "</div>"
                st.markdown(grid, unsafe_allow_html=True)
