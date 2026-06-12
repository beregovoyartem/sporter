import os
import sys

# Добавляем путь к sporter, чтобы импортировать parser_job
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser_job import sb_select, sb_upsert
from datetime import datetime, timedelta

def fix_times():
    print("Fetching all matches...")
    rows = sb_select("matches", "select=*")
    if not rows:
        print("No matches found or connection error.")
        return

    fixed_rows = []
    for r in rows:
        time_str = r.get("time")
        if not time_str: continue
        
        # Если время было сохранено как 2026-06-13T04:00:00+00:00, 
        # то оно имеет 'Z' или '+00:00'.
        # Мы знаем, что это было локальное время Livetv (UTC+3), ошибочно сохраненное как UTC.
        # То есть реальное время на 3 часа меньше.
        # Проверяем: если матч обновлялся ДО моего фикса (сегодня).
        # Мой фикс был сделан совсем недавно.
        # Если у матча time_str заканчивается на Z или +00:00
        
        try:
            # Парсим время
            if time_str.endswith("+00:00") or time_str.endswith("Z"):
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                # Убираем tzinfo, чтобы отнять 3 часа
                dt_naive = dt.replace(tzinfo=None)
            else:
                dt_naive = datetime.fromisoformat(time_str)
            
            # ВАЖНО: мы не знаем, был ли этот матч УЖЕ обновлен моим новым кодом.
            # Как отличить?
            # Новый код ставит 'Z' в конце: dt_utc.isoformat() + "Z" -> "2026-06-13T01:00:00Z"
            # Старый код: dt.isoformat() -> "2026-06-13T04:00:00" (без Z!)
            # Supabase добавляет +00:00 к результату sb_select, поэтому time_str из БД 
            # всегда имеет смещение +00:00 при выборке, НО!
            # У старого кода 'updated_at' тоже сохранялся через now = datetime.utcnow().isoformat() (БЕЗ Z).
            pass
        except:
            continue

if __name__ == "__main__":
    pass
