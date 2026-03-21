"""
styles.py — CSS для застосунку Sporter.
Єдина функція get_css(dark, clr, clrs, card, sb) → рядок стилів.
"""

def get_css(dark: bool, BG: str, CLR: str, CLRS: str, CARD: str, SB: str) -> str:
    """Повертає повний CSS застосунку."""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Pacifico&display=swap');
*{{box-sizing:border-box}}
html,body,[class*="css"]{{font-family:'Inter',sans-serif}}
.stApp{{{BG}min-height:100vh}}
#MainMenu,footer,header{{visibility:hidden}}
/* Ховаємо sidebar і бургер повністю */
section[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {{display:none!important}}
/* Скидаємо login-стилі + фікс зсуву контенту */
.block-container{{padding-top:0!important;max-width:1500px!important;position:relative!important;min-height:unset!important;display:block!important;justify-content:unset!important;flex-direction:unset!important;margin-left:0!important;}}
section[data-testid="stMain"]{{margin-left:0!important;}}
.lp-outer,.lp-title,.lp-sub,.lp-card,.lp-footer{{display:none!important}}

/* ── Topbar ── */
.sp-topbar{{
  display:flex;align-items:center;justify-content:space-between;
  padding:10px 0 8px;margin-bottom:4px;
  border-bottom:1px solid rgba(79,163,255,0.1);
}}
.sp-topbar-left{{display:flex;align-items:center;gap:10px;min-width:0}}
.sp-topbar-name{{font-size:.88em;font-weight:600;color:{CLRS};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:200px}}

/* Кнопки topbar — мінімальні, іконочні */
.sp-topbar + div[data-testid="stHorizontalBlock"] {{margin-top:-52px!important;float:right;width:auto!important;position:relative;z-index:10}}
.sp-topbar + div[data-testid="stHorizontalBlock"] .stButton > button {{
  background:rgba(79,163,255,0.07)!important;
  color:#8ab4d8!important;
  border:1px solid rgba(79,163,255,0.18)!important;
  border-radius:8px!important;
  height:34px!important;width:34px!important;min-width:34px!important;
  padding:0!important;font-size:1em!important;
  box-shadow:none!important;
  transition:background .15s,border-color .15s!important;
}}
.sp-topbar + div[data-testid="stHorizontalBlock"] .stButton > button:hover {{
  background:rgba(79,163,255,0.18)!important;
  border-color:rgba(79,163,255,0.45)!important;
  color:#dde6f5!important;
}}

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

.main-hdr{{display:flex;align-items:center;justify-content:space-between;padding:20px 0 16px;gap:12px;}}
.main-hdr-right{{display:flex;align-items:center;gap:10px;flex-shrink:0;}}
.hdr-update{{display:flex;align-items:center;gap:6px;font-size:.78em;font-weight:600;color:{CLRS};
  background:rgba(79,163,255,0.07);padding:5px 12px;border-radius:20px;
  border:1px solid rgba(79,163,255,0.15);white-space:nowrap;}}
.hdr-update svg{{opacity:.55;flex-shrink:0;}}

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

.mc.live{{border-color:rgba(79,163,255,0.2)!important}}
.mc.live::before{{background:linear-gradient(90deg,#1a6fff,#00c6ff);opacity:.6}}

/* ── топ (золота) ── */
.mc.top{{border-color:rgba(255,190,0,0.5)!important;
  background:linear-gradient(145deg,rgba(90,58,0,0.3),rgba(255,195,50,0.05))!important}}
.mc.top::before{{background:linear-gradient(90deg,#5a3a00,#ffd234,#5a3a00);
  background-size:200% 100%;opacity:1;animation:gs 3s linear infinite}}
@keyframes gs{{0%{{background-position:200% 0}}100%{{background-position:-200% 0}}}}

.mc.top.live{{border-color:rgba(255,190,0,0.6)!important;
  background:linear-gradient(145deg,rgba(90,58,0,0.35),rgba(255,195,50,0.07))!important}}

/* ── featured ── */
.mc.feat .tlogo{{width:60px;height:60px}}
.mc.feat .tlogo img{{width:54px;height:54px}}
.mc.feat .tph{{width:54px;height:54px;font-size:1.5em}}
.mc.feat .tname{{font-size:.78em;max-width:130px}}

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

/* ── топ картки: яскравість ободку за кількістю зірок ── */
.mc.top.stars1{{border-color:rgba(255,190,0,0.12)!important;box-shadow:none!important}}
.mc.top.stars2{{border-color:rgba(255,190,0,0.25)!important;box-shadow:none!important}}
.mc.top.stars3{{border-color:rgba(255,190,0,0.42)!important;box-shadow:0 0 8px rgba(255,185,0,0.07)!important}}
.mc.top.stars4{{border-color:rgba(255,190,0,0.62)!important;box-shadow:0 0 12px rgba(255,185,0,0.14)!important}}
.mc.top.stars5{{border-color:rgba(255,210,52,0.90)!important;box-shadow:0 0 20px rgba(255,185,0,0.28)!important}}

div[data-testid="stTabs"] button{{font-size:.75em!important;font-weight:600!important;color:{CLRS}!important}}
div[data-testid="stTabs"] button[aria-selected="true"]{{color:#4fa3ff!important}}

.stCheckbox label span{{font-size:.82em!important}}

[data-testid="stDialog"] > div > div{{
  background:rgba(8,15,36,0.97)!important;
  border:1px solid rgba(79,163,255,0.18)!important;
  border-radius:18px!important;
  box-shadow:0 8px 60px rgba(0,20,80,0.7)!important;
  max-width:860px!important;width:90vw!important;
}}
[data-testid="stDialog"] h3{{color:#dde6f5!important;font-size:1.1em!important}}
</style>
"""
