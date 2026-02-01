import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio
import sys
import threading

from .ui.main_window import MainWindow
from .ui.home_page import HomePage
from .data.database import init_db, get_session
from .data.models import Pokemon, Type, PokemonType, Ability, PokemonAbility, Region, Move, PokemonMove
from .hyprland.theme import load_css
from .hyprland.notifications import send_notification
from .utils import _load_image_in_thread

from sqlalchemy.orm import joinedload


class PokedexApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.archdex.pokedex",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window = None
        self.is_syncing = False
        self.main_window_content = None # This will be the Gtk.Box from MainWindow
        self.home_page = None
        self.header_bar = None
        self.search_timeout_id = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        # Initialize database in a background thread to avoid blocking UI startup
        threading.Thread(target=init_db, daemon=True).start()
        load_css() # Apply system GTK theme

    def do_activate(self):
        if not self.window:
            self.window = Gtk.ApplicationWindow(application=self, title="Pokedex")
            self.window.set_default_size(1200, 800)

            # Header Bar for the main application window
            self.header_bar = Gtk.HeaderBar()
            self.header_bar.set_show_close_button(True)
            self.header_bar.props.title = "Pokedex"
            self.window.set_titlebar(self.header_bar)

        if not self.home_page:
            self.home_page = HomePage(app_instance=self)
            
        self.window.add(self.home_page)
        self.home_page.show_all()
        self.window.present()

    def show_main_window(self):
        if not self.main_window_content:
            self.main_window_content = MainWindow(app_instance=self) # MainWindow is now a Gtk.Box
            
            # Add a toggle button for the sidebar to the header bar
            self.toggle_sidebar_button = Gtk.Button.new_from_icon_name("format-justify-left-symbolic", Gtk.IconSize.BUTTON)
            self.toggle_sidebar_button.connect("clicked", lambda x: self.main_window_content.toggle_sidebar())
            self.header_bar.pack_start(self.toggle_sidebar_button)

            # Add Check for Updates button to HeaderBar
            self.sync_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
            self.sync_button.set_tooltip_text("Check for Updates")
            self.sync_button.connect("clicked", lambda x: self.start_background_sync())
            self.header_bar.pack_end(self.sync_button)
            
            # Remove the search entry from header bar custom title (it's now in sidebar)
            self.header_bar.set_custom_title(None)
            self.header_bar.set_title("Pokedex")
            
            self.header_bar.show_all()

        # Switch the content of the main application window
        current_child = self.window.get_child()
        if current_child == self.main_window_content:
            return
        if current_child:
            self.window.remove(current_child)
        
        # Ensure it's not already parented elsewhere before adding
        parent = self.main_window_content.get_parent()
        if parent:
            parent.remove(self.main_window_content)
            
        self.window.add(self.main_window_content)
        self.main_window_content.show_all()
        self.window.present()
        self.on_search_changed(self.main_window_content.search_entry) # Trigger initial load for main window

    def _get_pokemon_from_db_in_thread(self, search_term, offset, limit, callback):
        session = get_session()
        query = session.query(Pokemon)
        
        if search_term:
            query = query.filter(Pokemon.name.ilike(f"%{search_term}%"))
        
        total_count = query.count()
        pokemon_list = query.order_by(Pokemon.id).offset(offset).limit(limit).all()
        
        session.close()
        GLib.idle_add(callback, pokemon_list, total_count)

    def on_search_changed(self, search_entry):
        if self.search_timeout_id:
            GLib.source_remove(self.search_timeout_id)
        
        self.search_timeout_id = GLib.timeout_add(300, self._perform_search, search_entry)

    def start_background_sync(self):
        if self.is_syncing:
            send_notification("Sync in Progress", "The database is already being updated.")
            return
        
        self.is_syncing = True
        send_notification("Update Started", "Checking for new Pokémon updates...")

        def run_sync():
            from .data.database import sync_database
            
            def progress(current, total):
                # We could update a progress bar here if we had one
                print(f"Sync progress: {current}/{total}")
            
            try:
                sync_database(background=True, progress_callback=progress)
                GLib.idle_add(send_notification, "Update Complete", "Pokémon database has been updated.")
            except Exception as e:
                GLib.idle_add(send_notification, "Update Failed", f"Error during sync: {str(e)}")
            finally:
                self.is_syncing = False
                # Refresh current view if we are in main window
                if self.main_window_content and self.window.get_child() == self.main_window_content:
                    GLib.idle_add(self.on_search_changed, self.main_window_content.search_entry)

        threading.Thread(target=run_sync, daemon=True).start()

    def _perform_search(self, search_entry):
        self.search_timeout_id = None
        search_term = search_entry.get_text().lower()
        
        # Show spinner before starting search
        self.main_window_content.spinner.show()
        self.main_window_content.spinner.start()
        
        offset = (self.main_window_content.current_page - 1) * self.main_window_content.items_per_page
        limit = self.main_window_content.items_per_page
        thread = threading.Thread(target=self._get_pokemon_from_db_in_thread, args=(search_term, offset, limit, self.main_window_content.update_pokemon_list))
        thread.daemon = True
        thread.start()
        return False # Don't repeat timeout

def main():
    app = PokedexApplication()
    return app.run(sys.argv)

if __name__ == "__main__":
    sys.exit(main())
