import os
from pathlib import Path

# Application Configuration

# Directory Settings
APP_NAME = "archdex"

def get_data_dir() -> Path:
    """Returns the platform-specific directory for application data."""
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        base_dir = Path(xdg_data_home)
    else:
        base_dir = Path.home() / ".local" / "share"
    
    data_dir = base_dir / APP_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

DATA_DIR = get_data_dir()
DATABASE_PATH = DATA_DIR / "pokedex.db"

# Window Settings
WINDOW_DEFAULT_WIDTH = 1200
WINDOW_DEFAULT_HEIGHT = 800
WINDOW_TITLE = "Pokedex"
APP_ID = "com.archdex.pokedex"

# Search Settings
SEARCH_TIMEOUT_MS = 300

# Pagination Settings
ITEMS_PER_PAGE = 50

# UI Settings
POKEMON_LIST_ICON_WIDTH = 48
POKEMON_LIST_ICON_HEIGHT = 48
SIDEBAR_WIDTH_REQUEST = 250
