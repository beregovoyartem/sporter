import re

with open("out.txt", "w", encoding="utf-8") as f:
    s1 = "Мексика МЕК"
    res1 = re.sub(r'\s+[А-ЯЁІЇЄҐA-Z]{3}$', '', s1)
    f.write(repr(res1) + "\n")
    s2 = "ЮАР ЮАР"
    res2 = re.sub(r'\s+[А-ЯЁІЇЄҐA-Z]{3}$', '', s2)
    f.write(repr(res2) + "\n")
