from pathlib import Path
from uni_ai_chatbot.resources import get_resource

def load_servery_hours() -> dict:
    file_path = get_resource(Path("servery_hours.txt"))
    data, college, period = {}, None, None

    with open(file_path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue

            if not line.startswith("-") and not line.endswith(":"):
                college = line
                data[college] = {}
                continue

            if line.endswith(":"):
                period = line[:-1].lower()
                data[college][period] = {}
                continue

            if line.startswith("-"):
                entry, hours = line[1:].split(":", 1)
                data[college][period][entry.strip().lower()] = hours.strip()

    return data
