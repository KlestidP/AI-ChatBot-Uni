from pathlib import Path


def get_resource(relative_path: Path) -> Path:
    return Path(__file__).parent.parent / "resources" / relative_path