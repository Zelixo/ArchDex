# Pokedex for aarch64 Linux with Hyprland

A Pokedex application built with Python and GTK, designed to work seamlessly in a Hyprland environment on aarch64 Linux systems.

## Features

*   Search functionality for Pokémon.
*   Detailed views for individual Pokémon (stats, abilities, types, etc.).
*   Local data storage using SQLite for offline access.
*   Hyprland theme integration.
*   Desktop notifications.

## Setup and Installation

### Prerequisites

*   Python 3.8+
*   GTK 3 development files (e.g., `libgtk-3-dev` on Debian/Ubuntu, `gtk3-devel` on Fedora)
*   GObject Introspection (e.g., `python3-gi`, `libgirepository1.0-dev`)

### Installation

#### From Source (Recommended for Development)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/ArchDex.git
    cd ArchDex
    ```

2.  **Install in editable mode:**
    ```bash
    pip install -e .
    ```

#### Native Arch Linux (AUR)

If you are on Arch Linux, you can build the package using the provided `PKGBUILD`:

```bash
makepkg -si
```

### Running the Application

After installation, you can run the app directly:

```bash
archdex
```

Or via Python:

```bash
python3 -m src.main
```

## Project Structure

```
.
├── src/
│   ├── main.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── detail_view.py
│   │   └── widgets.py
│   ├── data/
│   │   ├── database.py
│   │   ├── models.py
│   │   └── api.py
│   ├── hyprland/
│   │   ├── notifications.py
│   │   └── theme.py
│   └── __init__.py
├── tests/
│   ├── test_data.py
│   └── test_ui.py
├── data/
│   └── pokedex.db (Excluded from git)
├── assets/
│   └── icons/
├── requirements.txt
├── README.md
├── LICENSE
└── .gitignore
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
