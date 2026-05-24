import os
from pathlib import Path

def get_boilerplate_dir() -> Path:
    """Returns the path to the bundled boilerplate templates."""
    return Path(__file__).parent / "templates" / "boilerplate"
