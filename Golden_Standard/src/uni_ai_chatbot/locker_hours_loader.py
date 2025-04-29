from pathlib import Path
from uni_ai_chatbot.resources import get_resource
import re

def load_locker_hours():
    file_path = get_resource(Path("locker_hours.txt"))

    with open(file_path, encoding="utf-8") as f:
        lines = f.readlines()

    locker_hours = {}
    current_college = None
    current_day = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # --------- FIX ---------
        if "college" in line.lower():
            clean = re.sub(r"\s+", " ", line.replace("locker", "").strip())
            parts = clean.split(" ", 1)
            current_college = parts[0].capitalize() + (" " + parts[1] if len(parts) > 1 else "")
            locker_hours[current_college] = {}

        elif line.endswith(":") and any(day in line.lower() for day in ["monday", "thursday"]):
            current_day = line.replace(":", "").lower()
            locker_hours[current_college][current_day] = {}
        elif line.startswith("- Basement"):
            header, times = line.split(":", 1)
            basement = header.replace("- Basement", "").strip().upper()
            locker_hours[current_college][current_day][basement] = times.strip()

    return locker_hours
