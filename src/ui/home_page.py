import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib, Pango
import random
from datetime import datetime
import threading
from ..data.database import get_session
from ..data.models import Pokemon
from ..utils import _load_image_in_thread

class HomePage(Gtk.Box):
    def __init__(self, app_instance, *args, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20, *args, **kwargs)
        self.app_instance = app_instance
        self.set_margin_top(40)
        self.set_margin_bottom(40)
        self.set_margin_start(40)
        self.set_margin_end(40)

        # Header Section
        welcome_label = Gtk.Label(label="<span size='xx-large' weight='bold'>Welcome to ArchDex</span>")
        welcome_label.set_use_markup(True)
        self.pack_start(welcome_label, False, False, 10)

        subtitle_label = Gtk.Label(label="Your ultimate Linux-native Pokémon encyclopedia")
        subtitle_label.get_style_context().add_class("dim-label")
        self.pack_start(subtitle_label, False, False, 0)

        # Pokemon of the Day Section
        self.potd_frame = Gtk.Frame()
        self.potd_frame.set_label("Pokémon of the Day")
        self.potd_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.pack_start(self.potd_frame, True, True, 20)

        self.potd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.potd_box.set_margin_top(15)
        self.potd_box.set_margin_bottom(15)
        self.potd_frame.add(self.potd_box)

        self.potd_image = Gtk.Image()
        self.potd_image.set_pixel_size(256)
        self.potd_box.pack_start(self.potd_image, True, True, 0)

        self.potd_name_label = Gtk.Label()
        self.potd_name_label.set_use_markup(True)
        self.potd_box.pack_start(self.potd_name_label, False, False, 0)

        # Buttons Section
        button_box = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        button_box.set_layout(Gtk.ButtonBoxStyle.CENTER)
        self.pack_end(button_box, False, False, 10)

        start_button = Gtk.Button(label="View All Pokémon")
        start_button.get_style_context().add_class("suggested-action")
        start_button.set_size_request(200, 50)
        start_button.connect("clicked", self.on_start_button_clicked)
        button_box.pack_start(start_button, False, False, 0)

        sync_button = Gtk.Button(label="Check for Updates")
        sync_button.set_size_request(200, 50)
        sync_button.connect("clicked", self.on_sync_button_clicked)
        button_box.pack_start(sync_button, False, False, 0)

        # Load Pokémon of the Day
        threading.Thread(target=self.load_pokemon_of_the_day, daemon=True).start()

    def load_pokemon_of_the_day(self):
        # Use current date as seed for daily randomness
        seed = datetime.now().strftime("%Y%m%d")
        random.seed(seed)

        session = get_session()
        try:
            count = session.query(Pokemon).count()
            if count > 0:
                random_index = random.randint(0, count - 1)
                pokemon = session.query(Pokemon).offset(random_index).first()
                if pokemon:
                    GLib.idle_add(self.update_potd_ui, pokemon.name.capitalize(), pokemon.artwork_url or pokemon.sprite_url)
        except Exception as e:
            print(f"Error loading Pokémon of the Day: {e}")
        finally:
            session.close()

    def update_potd_ui(self, name, image_url):
        self.potd_name_label.set_markup(f"<span size='x-large' weight='semibold'>{name}</span>")
        if image_url:
            _load_image_in_thread(self.potd_image, image_url, 256, 256)

    def on_start_button_clicked(self, button):
        self.app_instance.show_main_window()

    def on_sync_button_clicked(self, button):
        self.app_instance.start_background_sync()
