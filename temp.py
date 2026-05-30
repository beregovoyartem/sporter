import requests, re
from bs4 import BeautifulSoup
r = requests.get('https://livetv.sx/allupcomingsports/1/', verify=False)
soup = BeautifulSoup(r.content.decode('windows-1251', errors='replace'), 'html.parser')
tds = soup.find_all('td', colspan="2")
for td in tds[:5]:
    a = td.find('a')
    if a:
        print(repr(a.get_text(strip=True)))
