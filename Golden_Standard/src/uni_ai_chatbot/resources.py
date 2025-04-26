from pathlib import Path


def get_resource(relative_path: Path) -> Path:
    return Path(__file__).parent.parent / "resources" / relative_path


def load_locker_hours():
    file_path = get_resource(Path("locker_hours.txt"))
    locker_data = {}

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_college = None
    current_day = None

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if "College" in line:
            current_college = line
            locker_data[current_college] = {}
        elif line.lower() == "monday:":
            current_day = "monday"
            locker_data[current_college][current_day] = {}
        elif line.lower() == "thursday:":
            current_day = "thursday"
            locker_data[current_college][current_day] = {}
        elif line.startswith("- Basement"):
            try:
                parts = line.split(":")
                basement = parts[0].split()[-1]
                hours = parts[1].strip()
                locker_data[current_college][current_day][basement] = hours
            except Exception:
                continue

    return locker_data
