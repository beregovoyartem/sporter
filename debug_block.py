"""
debug_block.py — перевіряємо чи блокує livetv.sx запити з цього IP.
Запусти через GitHub Actions workflow_dispatch і скинь лог.
"""
import requests
import urllib3
import socket

urllib3.disable_warnings()

HDR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
}

print(f"IP цієї машини: ", end="", flush=True)
try:
    ip = requests.get("https://api.ipify.org", timeout=5).text
    print(ip, flush=True)
except:
    print("невідомо", flush=True)

# Тест 1: головна сторінка
print("\n=== Тест 1: головна сторінка розкладу ===")
try:
    r = requests.get("https://livetv.sx/allupcomingsports/1/", timeout=10, headers=HDR, verify=False)
    print(f"  Status: {r.status_code}, розмір: {len(r.text)} байт")
except Exception as e:
    print(f"  ПОМИЛКА: {e}")

# Тест 2: сторінка конкретного матчу
print("\n=== Тест 2: сторінка матчу (Брайтон-Ліверпуль) ===")
url = "https://livetv.sx/eventinfo/351331873_brayton_liverpul/"
try:
    r = requests.get(url, timeout=10, headers=HDR, verify=False)
    print(f"  Status: {r.status_code}, розмір: {len(r.text)} байт")
    # Чи є логотипи?
    import re
    cdn = re.findall(r'cdn\.livetv\d+\.me/img/teams/[^\s"\'<>]+\.gif', r.text)
    print(f"  CDN логотипів знайдено: {len(set(cdn))}")
    for u in set(cdn):
        print(f"    {u}")
    # JSON-LD
    import json
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r.text, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if "image" in data:
                print(f"  JSON-LD images: {data['image']}")
        except: pass
except Exception as e:
    print(f"  ПОМИЛКА: {e}")

# Тест 3: CDN логотип напряму
print("\n=== Тест 3: завантаження логотипу з CDN ===")
logo_url = "https://cdn.livetv873.me/img/teams/fullsize/ods/1110.gif"
try:
    r = requests.get(logo_url, timeout=8, headers={"User-Agent": HDR["User-Agent"]}, verify=False)
    print(f"  Status: {r.status_code}, розмір: {len(r.content)} байт")
except Exception as e:
    print(f"  ПОМИЛКА: {e}")

print("\nГотово!")
