import os
from parser_job import sb_select

rows = sb_select("matches", "limit=5&order=updated_at.desc")
for r in rows:
    print(f"{r['title']} -> {r['time']} | Status: {r['status']}")
