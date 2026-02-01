import gi
import threading
from typing import List, Optional, Any
from sqlalchemy.orm import joinedload
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib, Gio

# Import the image loading function from utils.py
from ..utils import _load_image_in_thread, image_executor

from .detail_view import DetailView
from ..data.database import is_pokemon_data_complete, update_pokemon_data, get_session
from ..data.models import Pokemon, PokemonType, PokemonAbility, PokemonMove, Move

from ..config import (
    ITEMS_PER_PAGE,
    POKEMON_LIST_ICON_WIDTH,
    POKEMON_LIST_ICON_HEIGHT,
    SIDEBAR_WIDTH_REQUEST
)

class PokemonListItem(Gtk.ListBoxRow):
    def __init__(self, pokemon_data: Pokemon) -> None:
        super().__init__()
        self.pokemon_data = pokemon_data

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_border_width(5)
        self.add(hbox)

        # Placeholder for image
        self.image = Gtk.Image()
        hbox.pack_start(self.image, False, False, 0)
        
        # Load image in a background thread
        image_executor.submit(_load_image_in_thread, self.image, pokemon_data.sprite_url, POKEMON_LIST_ICON_WIDTH, POKEMON_LIST_ICON_HEIGHT)

        label = Gtk.Label(label=pokemon_data.name.capitalize())
        label.set_xalign(0)
        hbox.pack_start(label, True, True, 0)


class MainWindow(Gtk.Box):
    def __init__(self, app_instance: Any, *args: Any, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, *args, **kwargs)
        self.app_instance = app_instance
        
        # Sidebar (Left Side) - Now a Revealer for collapsibility
        self.sidebar_revealer = Gtk.Revealer()
        self.sidebar_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.sidebar_revealer.set_reveal_child(True)
        self.pack_start(self.sidebar_revealer, False, False, 0)

        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.sidebar.set_size_request(SIDEBAR_WIDTH_REQUEST, -1)
        self.sidebar_revealer.add(self.sidebar)

        # Search Entry (moved from HeaderBar to Sidebar)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search Pokémon...")
        self.search_entry.set_margin_start(10)
        self.search_entry.set_margin_end(10)
        self.search_entry.set_margin_top(10)
        self.search_entry.connect("search-changed", self.app_instance.on_search_changed)
        self.sidebar.pack_start(self.search_entry, False, False, 0)

        # ListBox for Pokemon results in a scrolled window
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.sidebar.pack_start(scrolled_window, True, True, 0)

        self.pokemon_list_box = Gtk.ListBox()
        self.pokemon_list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.pokemon_list_box.connect("row-activated", self.on_pokemon_selected)
        scrolled_window.add(self.pokemon_list_box)

        # Loading Spinner
        self.spinner = Gtk.Spinner()
        self.sidebar.pack_start(self.spinner, False, False, 10)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.pack_start(separator, False, False, 0)

        # Main Content Area (Right Side)
        self.detail_view = DetailView()
        self.pack_start(self.detail_view, True, True, 0)

        # Pagination attributes
        self.current_page: int = 1
        self.items_per_page: int = ITEMS_PER_PAGE  # Increased for better use of space
        self.total_pokemon_count: int = 0

        # Pagination controls
        self.pagination_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.pagination_box.set_halign(Gtk.Align.CENTER)
        self.sidebar.pack_end(self.pagination_box, False, False, 10)

        self.first_button = Gtk.Button.new_from_icon_name("go-first-symbolic", Gtk.IconSize.BUTTON)
        self.first_button.connect("clicked", self.on_first_page)
        self.pagination_box.pack_start(self.first_button, False, False, 0)

        self.prev_button = Gtk.Button.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON)
        self.prev_button.connect("clicked", self.on_prev_page)
        self.pagination_box.pack_start(self.prev_button, False, False, 0)

        self.page_label = Gtk.Label(label="1/1")
        self.page_label.set_margin_start(5)
        self.page_label.set_margin_end(5)
        self.pagination_box.pack_start(self.page_label, False, False, 0)

        self.next_button = Gtk.Button.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON)
        self.next_button.connect("clicked", self.on_next_page)
        self.pagination_box.pack_start(self.next_button, False, False, 0)

        self.last_button = Gtk.Button.new_from_icon_name("go-last-symbolic", Gtk.IconSize.BUTTON)
        self.last_button.connect("clicked", self.on_last_page)
        self.pagination_box.pack_start(self.last_button, False, False, 0)

    def toggle_sidebar(self) -> None:
        is_revealed = self.sidebar_revealer.get_reveal_child()
        self.sidebar_revealer.set_reveal_child(not is_revealed)

    def on_pokemon_selected(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        if isinstance(row, PokemonListItem):
            pokemon_data = row.pokemon_data
            
            # Use a thread to check and update/show pokemon
            def check_and_show() -> None:
                session = get_session()
                try:
                    # Re-fetch pokemon with relations
                    pokemon = session.query(Pokemon).options(
                        joinedload(Pokemon.region),
                        joinedload(Pokemon.types).joinedload(PokemonType.type),
                        joinedload(Pokemon.abilities).joinedload(PokemonAbility.ability),
                        joinedload(Pokemon.moves).joinedload(PokemonMove.move).joinedload(Move.type)
                    ).filter(Pokemon.id == pokemon_data.id).first()

                    if not is_pokemon_data_complete(pokemon):
                        pokemon = update_pokemon_data(session, pokemon.id)
                    
                    if pokemon:
                        GLib.idle_add(self.detail_view.update_data, pokemon)
                except Exception as e:
                    print(f"Error loading pokemon details: {e}")
                finally:
                    session.close()

            threading.Thread(target=check_and_show, daemon=True).start()

    def update_pokemon_list(self, pokemon_data_list: List[Pokemon], total_count: int) -> None:
        # Clear existing list
        self.pokemon_list_box.foreach(lambda row: self.pokemon_list_box.remove(row))
        self.total_pokemon_count = total_count

        # Add new items
        for pokemon_data in pokemon_data_list:
            item = PokemonListItem(pokemon_data)
            self.pokemon_list_box.add(item)
        
        self.spinner.stop()
        self.spinner.hide()
        self.pokemon_list_box.show_all()
        self._update_pagination_ui()

    def _update_pagination_ui(self) -> None:
        total_pages = (self.total_pokemon_count + self.items_per_page - 1) // self.items_per_page
        self.page_label.set_text(f"{self.current_page} / {max(1, total_pages)}")
        self.first_button.set_sensitive(self.current_page > 1)
        self.prev_button.set_sensitive(self.current_page > 1)
        self.next_button.set_sensitive(self.current_page < total_pages)
        self.last_button.set_sensitive(self.current_page < total_pages)

    def on_first_page(self, button: Gtk.Button) -> None:
        if self.current_page != 1:
            self.current_page = 1
            self.app_instance.on_search_changed(self.search_entry)

    def on_prev_page(self, button: Gtk.Button) -> None:
        if self.current_page > 1:
            self.current_page -= 1
            self.app_instance.on_search_changed(self.search_entry)

    def on_next_page(self, button: Gtk.Button) -> None:
        total_pages = (self.total_pokemon_count + self.items_per_page - 1) // self.items_per_page
        if self.current_page < total_pages:
            self.current_page += 1
            self.app_instance.on_search_changed(self.search_entry)

    def on_last_page(self, button: Gtk.Button) -> None:
        total_pages = (self.total_pokemon_count + self.items_per_page - 1) // self.items_per_page
        if self.current_page != total_pages:
            self.current_page = total_pages
            self.app_instance.on_search_changed(self.search_entry)
