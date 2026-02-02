import gi
import os
from collections import defaultdict
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib, Gio, Gdk, Pango
import threading

# Import the image loading function from utils.py
from ..utils import _load_image_in_thread
from ..data.models import Pokemon, Ability, Move, Type, Region
from ..data.api import _fetch_data, get_species_varieties
from sqlalchemy.orm import joinedload

import math

def _get_stat_color(value: int):
    if value < 30:
        return "#F34444"  # Very Poor
    elif value < 60:
        return "#FF7F0F"  # Poor
    elif value < 90:
        return "#FFDD57"  # Average
    elif value < 120:
        return "#A0E515"  # Good
    elif value < 150:
        return "#23CD5E"  # Very Good
    else:
        return "#00C2B8"  # Phenomenal

TYPE_COLORS = {
    "normal": "#A8A77A",
    "fire": "#EE8130",
    "water": "#6390F0",
    "electric": "#F7D02C",
    "grass": "#7AC74C",
    "ice": "#96D9D6",
    "fighting": "#C22E28",
    "poison": "#A33EA1",
    "ground": "#E2BF65",
    "flying": "#A98FF3",
    "psychic": "#F95587",
    "bug": "#A6B91A",
    "rock": "#B6A136",
    "ghost": "#735797",
    "dragon": "#6F35FC",
    "dark": "#705746",
    "steel": "#B7B7CE",
    "fairy": "#D685AD",
}

def get_asset_path(asset_relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller/package"""
    import sys
    from pathlib import Path
    
    # Try package-relative path first (when installed)
    try:
        from importlib import resources
        # This works if assets is treated as a package, but it's not.
        # So we use the file-relative path but more robustly.
        pass
    except ImportError:
        pass

    # Base directory of the current file
    base_path = Path(__file__).parent.parent.parent
    
    # Check if we are running in a site-packages/archdex/ui directory
    # or in the source tree src/ui
    asset_path = base_path / asset_relative_path
    if asset_path.exists():
        return str(asset_path)
        
    # Fallback for some packaging layouts
    return str(Path(sys.prefix) / "share" / "archdex" / asset_relative_path)

CATEGORY_ICONS = {
    "physical": get_asset_path("assets/icons/physical.png"),
    "special": get_asset_path("assets/icons/special.png"),
    "status": get_asset_path("assets/icons/status.png"),
}

VERSION_GROUPS = {
    "red-blue": "Gen 1", "yellow": "Gen 1",
    "gold-silver": "Gen 2", "crystal": "Gen 2",
    "ruby-sapphire": "Gen 3", "emerald": "Gen 3", "firered-leafgreen": "Gen 3",
    "diamond-pearl": "Gen 4", "platinum": "Gen 4", "heartgold-soulsilver": "Gen 4",
    "black-white": "Gen 5", "black-2-white-2": "Gen 5",
    "x-y": "Gen 6", "omega-ruby-alpha-sapphire": "Gen 6",
    "sun-moon": "Gen 7", "ultra-sun-ultra-moon": "Gen 7", "lets-go-pikachu-lets-go-eevee": "Gen 7",
    "sword-shield": "Gen 8", "brilliant-diamond-shining-pearl": "Gen 8", "legends-arceus": "Gen 8",
    "scarlet-violet": "Gen 9"
}

ALL_GENERATIONS = ["Gen 1", "Gen 2", "Gen 3", "Gen 4", "Gen 5", "Gen 6", "Gen 7", "Gen 8", "Gen 9"]

# Max Pokémon ID for each generation
GEN_MAX_ID = {
    "Gen 1": 151,
    "Gen 2": 251,
    "Gen 3": 386,
    "Gen 4": 493,
    "Gen 5": 649,
    "Gen 6": 721,
    "Gen 7": 809,
    "Gen 8": 905,
    "Gen 9": 2000
}

class DetailView(Gtk.ScrolledWindow):
    def __init__(self, pokemon_data: Pokemon = None):
        super().__init__()
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.pokemon_data = None
        self.generation_combo = None
        self._active_main_tab = 0
        self._active_moves_tab = 0

        self.viewport = Gtk.Viewport()
        self.add(self.viewport)

        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.main_box.set_border_width(10)
        self.viewport.add(self.main_box)

        if pokemon_data:
            self.update_data(pokemon_data)
        else:
            self._show_empty_state()

    def _show_empty_state(self):
        # Clear existing content
        for child in self.main_box.get_children():
            self.main_box.remove(child)
        
        label = Gtk.Label(label="Select a Pokémon to see details")
        label.set_margin_top(50)
        self.main_box.pack_start(label, True, True, 0)
        self.show_all()

    def update_data(self, pokemon_data: Pokemon):
        # Reset tab indices for a new Pokemon (species change)
        if self.pokemon_data and self.pokemon_data.species_url != pokemon_data.species_url:
            self._active_main_tab = 0
            self._active_moves_tab = 0
        self.pokemon_data = pokemon_data
        
        # Check if data is complete, if not, fetch it in a thread
        from ..data.database import update_pokemon_data, get_session
        from ..data.models import PokemonType, PokemonAbility, PokemonMove, Move
        
        # DetachedInstanceError prevention: re-fetch with all eager loads
        def check_completeness_and_render():
            from ..data.database import is_pokemon_data_complete
            session = get_session()
            try:
                # Re-query with all necessary joinedloads for rendering
                query = session.query(Pokemon).options(
                    joinedload(Pokemon.region),
                    joinedload(Pokemon.types).joinedload(PokemonType.type),
                    joinedload(Pokemon.abilities).joinedload(PokemonAbility.ability),
                    joinedload(Pokemon.moves).joinedload(PokemonMove.move).joinedload(Move.type)
                )
                attached_pokemon = query.filter_by(id=pokemon_data.id).first()

                if not attached_pokemon or not is_pokemon_data_complete(attached_pokemon):
                    GLib.idle_add(self._show_loading_state)
                    # update_pokemon_data re-fetches internally but we need the eager loaded version after update
                    update_pokemon_data(session, pokemon_data.id)
                    # Re-fetch after update to get the new data with joinedloads
                    attached_pokemon = query.filter_by(id=pokemon_data.id).first()
                
                if attached_pokemon:
                    # Detach all related objects from session by accessing them
                    # Or just pass the data we need. Actually, keeping session open
                    # until render is done might be safest if we can't easily detach everything.
                    # But GLib.idle_add runs later.
                    
                    # Force loading of attributes while session is open
                    _ = attached_pokemon.region
                    for pt in attached_pokemon.types: _ = pt.type
                    for pa in attached_pokemon.abilities: _ = pa.ability
                    for pm in attached_pokemon.moves:
                        _ = pm.move
                        if pm.move: _ = pm.move.type

                    GLib.idle_add(self._render_details, attached_pokemon)
            except Exception as e:
                print(f"Error checking completeness: {e}")
            finally:
                session.close()

        threading.Thread(target=check_completeness_and_render, daemon=True).start()
        return

        self._render_details(pokemon_data)

    def _show_loading_state(self):
        for child in self.main_box.get_children():
            self.main_box.remove(child)
        spinner = Gtk.Spinner()
        spinner.start()
        self.main_box.pack_start(spinner, True, True, 0)
        self.main_box.pack_start(Gtk.Label(label="Fetching detailed data..."), False, False, 0)
        self.show_all()

    def _lazy_load_data(self, pokemon_id, species_url):
        from ..data.database import update_pokemon_data, get_session
        session = get_session()
        updated_pokemon = update_pokemon_data(session, pokemon_id, pokemon_url=None) # update_pokemon_data now handles checks
        session.close()
        
        if updated_pokemon:
            GLib.idle_add(self._render_details, updated_pokemon)

    def _render_details(self, pokemon_data: Pokemon, selected_generation: str = None):
        # Freeze UI updates for performance
        self.main_box.freeze_child_notify()
        # Save current tab indices if notebooks exist
        # We need to find them in the current main_box before clearing
        for child in self.main_box.get_children():
            if isinstance(child, Gtk.Box): # top_box
                for subchild in child.get_children():
                    if isinstance(subchild, Gtk.Box): # main_h_box
                        # The notebook is the second child of main_h_box
                        h_box_children = subchild.get_children()
                        if len(h_box_children) >= 2:
                            right_side = h_box_children[1]
                            if isinstance(right_side, Gtk.Notebook):
                                self._active_main_tab = right_side.get_current_page()
                                # Try to find moves_notebook
                                moves_page = right_side.get_nth_page(0)
                                if isinstance(moves_page, Gtk.Box):
                                    for moves_child in moves_page.get_children():
                                        if isinstance(moves_child, Gtk.Notebook):
                                            self._active_moves_tab = moves_child.get_current_page()

        # Clear existing content
        for child in self.main_box.get_children():
            self.main_box.remove(child)

        # Container for the top part (Name, Image, Types, etc.)
        self.top_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.main_box.pack_start(self.top_box, True, True, 0)

        # Top Bar with Title and Generation Selector
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.top_box.pack_start(top_bar, False, False, 0)

        # Pokémon Name and ID
        name_text = pokemon_data.name.capitalize()
        if pokemon_data.form_name:
            name_text += f" ({pokemon_data.form_name.replace('-', ' ').capitalize()})"
            
        name_id_label = Gtk.Label()
        name_id_label.set_markup(f"<span size='xx-large'><b>{name_text}</b></span> <span size='large' foreground='#888'>#{pokemon_data.id}</span>")
        name_id_label.set_xalign(0)
        top_bar.pack_start(name_id_label, True, True, 0)

        # Generation filter combobox
        gen_filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        gen_filter_box.set_halign(Gtk.Align.END)
        gen_label = Gtk.Label(label="Generation:")
        gen_filter_box.pack_start(gen_label, False, False, 0)
        
        self.generation_combo = Gtk.ComboBoxText()
        for gen in ALL_GENERATIONS:
            self.generation_combo.append_text(gen)
        
        # Check if Pokémon existed in selected generation
        pokemon_first_gen = 10
        for pm in pokemon_data.moves:
            v_group = pm.version_group
            if v_group and v_group != "unknown":
                gen_name = VERSION_GROUPS.get(v_group, "")
                if gen_name.startswith("Gen "):
                    try:
                        gen_num = int(gen_name.split(" ")[1])
                        if gen_num < pokemon_first_gen:
                            pokemon_first_gen = gen_num
                    except: pass

        if not selected_generation:
            # Default to the generation the Pokémon was introduced in
            pokemon_first_gen_str = f"Gen {pokemon_first_gen}" if pokemon_first_gen <= 9 else "Gen 9"
            try:
                idx = ALL_GENERATIONS.index(pokemon_first_gen_str)
                self.generation_combo.set_active(idx)
                selected_generation = pokemon_first_gen_str
            except ValueError:
                self.generation_combo.set_active(0)
                selected_generation = "Gen 1"
        else:
            try:
                idx = ALL_GENERATIONS.index(selected_generation)
                self.generation_combo.set_active(idx)
            except ValueError:
                self.generation_combo.set_active(0)
                selected_generation = ALL_GENERATIONS[0]
        
        self.generation_combo.connect("changed", self._on_generation_changed)
        gen_filter_box.pack_start(self.generation_combo, False, False, 0)
        top_bar.pack_start(gen_filter_box, False, False, 0)

        try:
            selected_gen_num = int(selected_generation.split(" ")[1])
            if selected_gen_num < pokemon_first_gen:
                not_discovered_label = Gtk.Label()
                not_discovered_label.set_markup(f"<span foreground='#f44336' size='large'><b>Note:</b> This Pokémon was not discovered until Gen {pokemon_first_gen}.</span>")
                not_discovered_label.set_xalign(0)
                self.top_box.pack_start(not_discovered_label, False, False, 0)
        except: pass

        # Main horizontal box container (no longer a Paned to lock the ratio)
        main_h_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.top_box.pack_start(main_h_box, True, True, 0)

        # Left Column: Image, Stats, Info
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        left_box.set_border_width(5)
        main_h_box.pack_start(left_box, True, True, 0)


        # Top Row: Image (Left) and General Info (Right)
        top_row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        left_box.pack_start(top_row_box, False, False, 0)

        # Image - Official Artwork (increased by another 50% from 156x156 -> 234x234)
        self.artwork_image = Gtk.Image()
        top_row_box.pack_start(self.artwork_image, False, False, 0)
        
        thread = threading.Thread(target=_load_image_in_thread, args=(self.artwork_image, pokemon_data.artwork_url, 234, 234))
        thread.daemon = True
        thread.start()

        # Basic Info to the right of the image
        info_grid = Gtk.Grid()
        info_grid.set_column_spacing(10)
        info_grid.set_row_spacing(5)
        info_grid.set_valign(Gtk.Align.CENTER)
        top_row_box.pack_start(info_grid, True, True, 0)
        
        info_data = [
            ("Height", f"{pokemon_data.height/10} m"),
            ("Weight", f"{pokemon_data.weight/10} kg"),
            ("Base XP", str(pokemon_data.base_experience or "N/A")),
            ("Region", pokemon_data.region.name.capitalize() if pokemon_data.region else "Unknown")
        ]
        
        for i, (label, val) in enumerate(info_data):
            info_grid.attach(Gtk.Label(label=f"<b>{label}:</b>", use_markup=True, xalign=0), 0, i, 1, 1)
            info_grid.attach(Gtk.Label(label=val, xalign=0), 1, i, 1, 1)

        # Types
        types_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        types_box.set_halign(Gtk.Align.START)
        left_box.pack_start(types_box, False, False, 0)
        for pt in pokemon_data.types:
            type_label = Gtk.Label()
            color = TYPE_COLORS.get(pt.type.name.lower(), "#444")
            type_label.set_markup(f"<span background='{color}' foreground='white'>  {pt.type.name.capitalize()}  </span>")
            types_box.pack_start(type_label, False, False, 0)

        # Description
        description_label = Gtk.Label(label=pokemon_data.description)
        description_label.set_line_wrap(True)
        description_label.set_max_width_chars(45)
        description_label.set_margin_top(10)
        description_label.set_margin_bottom(10)
        description_label.set_xalign(0)
        left_box.pack_start(description_label, False, False, 0)

        # Base Stats in an Expander
        base_stats_expander = Gtk.Expander(label="Base Stats")
        base_stats_expander.set_expanded(True)
        left_box.pack_start(base_stats_expander, False, False, 0)

        stats_grid = Gtk.Grid()
        stats_grid.set_column_spacing(10)
        stats_grid.set_row_spacing(6)
        stats_grid.set_border_width(10)
        base_stats_expander.add(stats_grid)

        stats_order = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
        stats_display_names = {"hp": "HP", "attack": "Atk", "defense": "Def", "special_attack": "SpA", "special_defense": "SpD", "speed": "Spe"}
        MAX_STAT_VALUE = 255

        # Apply CSS for progress bar coloring
        for i, stat_name in enumerate(stats_order):
            value = getattr(pokemon_data, stat_name, 0)
            name_label = Gtk.Label(label=f"<span size='large'><b>{stats_display_names[stat_name]}:</b></span>")
            name_label.set_use_markup(True)
            name_label.set_xalign(0)
            stats_grid.attach(name_label, 0, i, 1, 1)

            value_label = Gtk.Label(label=f"<span size='large'>{value}</span>")
            value_label.set_use_markup(True)
            value_label.set_xalign(1)
            value_label.set_size_request(40, -1)
            stats_grid.attach(value_label, 1, i, 1, 1)

            progress_bar = Gtk.ProgressBar()
            progress_bar.set_fraction(value / MAX_STAT_VALUE)
            progress_bar.set_hexpand(True)
            progress_bar.set_size_request(-1, 18)

            # Set custom CSS for the progress bar
            color_hex = _get_stat_color(value)
            css = f"progressbar > trough > progress {{ background-color: {color_hex}; min-height: 15px; }}"
            # Each progress bar needs its own CSS styling.
            # Create a new CssProvider for each progress bar
            # to avoid conflicts and ensure independent styling.
            bar_style_provider = Gtk.CssProvider()
            bar_style_provider.load_from_data(css.encode('utf-8'))
            context = progress_bar.get_style_context()
            context.add_provider(bar_style_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

            stats_grid.attach(progress_bar, 2, i, 1, 1)

        # Right Column: Notebook for Moves, Abilities, Evolutions
        right_notebook = Gtk.Notebook()
        main_h_box.pack_start(right_notebook, True, True, 0)

        # Tab 1: Moves
        moves_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        moves_box.set_border_width(5)


        # Nested Notebook for Move Categories
        moves_notebook = Gtk.Notebook()
        moves_box.pack_start(moves_notebook, True, True, 0)

        def create_scrolled_box():
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            box.set_border_width(5)
            scrolled.add(box)
            return scrolled, box

        self.level_up_scroll, self.level_up_box = create_scrolled_box()
        moves_notebook.append_page(self.level_up_scroll, Gtk.Label(label="Level Up"))

        self.egg_scroll, self.egg_box = create_scrolled_box()
        moves_notebook.append_page(self.egg_scroll, Gtk.Label(label="Egg Moves"))

        self.machine_scroll, self.machine_box = create_scrolled_box()
        moves_notebook.append_page(self.machine_scroll, Gtk.Label(label="TM/HM"))

        # Custom sort for generations
        def gen_sort_key_for_display(gen):
            if gen.startswith("Gen "):
                try:
                    return int(gen.split(" ")[1])
                except:
                    return 99
            return 100

        # Group and filter moves by generation, then by method
        filtered_gen_moves = defaultdict(lambda: defaultdict(list))
        seen_moves_in_filtered_gen = set()
        for pm in pokemon_data.moves:
            v_group = pm.version_group
            gen_name_for_move = "Other"
            if v_group and v_group != "unknown":
                gen_name_for_move = VERSION_GROUPS.get(v_group, v_group.replace("-", " ").capitalize())
            
            if gen_name_for_move == selected_generation:
                move_gen_key = (gen_name_for_move, pm.move.name, pm.learn_method, pm.level_learned_at)
                if move_gen_key not in seen_moves_in_filtered_gen:
                    filtered_gen_moves[gen_name_for_move][pm.learn_method].append(pm)
                    seen_moves_in_filtered_gen.add(move_gen_key)

        # Render filtered moves into their respective category boxes
        methods = [
            ("level-up", "Level Up Moves", True, self.level_up_box),
            ("egg", "Egg Moves", False, self.egg_box),
            ("machine", "TM/HM Moves", False, self.machine_box)
        ]

        for method_id, method_label, is_level_up, target_box in methods:
            # Group by generation within each category if "All Generations" is selected
            for gen in sorted(filtered_gen_moves.keys(), key=gen_sort_key_for_display):
                moves_list = filtered_gen_moves[gen].get(method_id, [])
                if not moves_list:
                    continue
                
                self._render_moves_section(target_box, moves_list, method_id, method_label, gen, is_level_up)

        right_notebook.append_page(moves_box, Gtk.Label(label="Moves"))

        # Tab 2: Abilities
        abilities_scroll = Gtk.ScrolledWindow()
        abilities_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        abilities_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        abilities_box.set_border_width(5)
        abilities_scroll.add(abilities_box)

        # Use a horizontal box to put abilities and effectiveness side-by-side
        # to avoid vertical scrolling and use blank space.
        side_by_side_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        abilities_box.pack_start(side_by_side_box, True, True, 0)

        abilities_left_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        side_by_side_box.pack_start(abilities_left_column, True, True, 0)

        effectiveness_right_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        side_by_side_box.pack_start(effectiveness_right_column, True, True, 0)

        # Abilities section in left column
        gen_num = int(selected_generation.split(" ")[1])
        
        if gen_num < 3:
            abilities_left_column.pack_start(Gtk.Label(label="Abilities were introduced in Gen 3."), False, False, 10)
        else:
            for pa in pokemon_data.abilities:
                # Hidden abilities were introduced in Gen 5
                if pa.is_hidden and gen_num < 5:
                    continue
                    
                ability_name = pa.ability.name.replace('-', ' ').capitalize()
                hidden_tag = " (Hidden)" if pa.is_hidden else ""
                
                frame = Gtk.Frame()
                frame.set_label(f"{ability_name}{hidden_tag}")
                abilities_left_column.pack_start(frame, False, False, 2)

                a_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                a_box.set_border_width(4)
                frame.add(a_box)
                
                desc_lbl = Gtk.Label(label=pa.ability.short_description or pa.ability.description)
                desc_lbl.set_line_wrap(True)
                desc_lbl.set_xalign(0)
                desc_lbl.set_max_width_chars(35) # Reduced to fit side-by-side
                a_box.pack_start(desc_lbl, False, False, 0)

        # Type Effectiveness section in right column
        eff_frame = Gtk.Frame()
        eff_frame.set_label("Type Effectiveness")
        effectiveness_right_column.pack_start(eff_frame, True, True, 0)

        self.effectiveness_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.effectiveness_box.set_border_width(5)
        eff_frame.add(self.effectiveness_box)

        # Pass current types to avoid DetachedInstanceError in the background thread
        current_types_list = list(pokemon_data.types)
        threading.Thread(target=self._load_weaknesses, args=(selected_generation, current_types_list)).start()
        
        right_notebook.append_page(abilities_scroll, Gtk.Label(label="Abilities"))

        # Tab 3: Evolutions
        # Tab 3: Evolutions - Use a ScrolledWindow for better scaling handling
        self.evo_scroll = Gtk.ScrolledWindow()
        self.evo_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.evo_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        self.evo_box.set_border_width(20)
        self.evo_box.set_halign(Gtk.Align.CENTER)
        self.evo_box.set_valign(Gtk.Align.CENTER)
        self.evo_scroll.add(self.evo_box)
        right_notebook.append_page(self.evo_scroll, Gtk.Label(label="Evolutions"))

        # Tab 4: Forms
        self.forms_scroll = Gtk.ScrolledWindow()
        self.forms_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.varieties_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.varieties_box.set_border_width(10)
        self.forms_scroll.add(self.varieties_box)
        self.forms_tab_label = Gtk.Label(label="Forms")
        right_notebook.append_page(self.forms_scroll, self.forms_tab_label)

        if pokemon_data.species_url:
            threading.Thread(target=self._load_varieties, args=(pokemon_data.species_url,)).start()
        
        # Restore tab indices
        right_notebook.set_current_page(self._active_main_tab)
        moves_notebook.set_current_page(self._active_moves_tab)

        if pokemon_data.evolution_chain_url:
            threading.Thread(target=self._load_evolutions, args=(selected_generation,)).start()
        else:
            self.evo_box.pack_start(Gtk.Label(label="No evolution data."), True, True, 0)

        self.show_all()



    def _on_generation_changed(self, combo_box):
        selected_generation = combo_box.get_active_text()
        if not self.pokemon_data:
            return
        self._render_details(self.pokemon_data, selected_generation)

    def _load_weaknesses(self, selected_generation, current_types=None):
        if not self.pokemon_data: return
        
        # Use types passed from attached object, or try to access self.pokemon_data.types
        # (the latter might still fail if called independently, but render_details passes them now)
        if current_types is None:
            try:
                current_types = self.pokemon_data.types
            except:
                return
        
        if not current_types: return

        # Determine available types for this generation
        available_types = list(TYPE_COLORS.keys())
        gen_num = int(selected_generation.split(" ")[1])
        if gen_num < 2:
            available_types = [t for t in available_types if t not in ["steel", "dark"]]
        if gen_num < 6:
            available_types = [t for t in available_types if t not in ["fairy"]]

        effectiveness = {t: 1.0 for t in available_types}
        
        for pt in current_types:
            # If the Pokémon's type didn't exist in the selected generation, skip it?
            # Or handle type changes (e.g. Clefairy was Normal before Gen 6)
            # For now, let's just filter the attacking types.
            
            type_data = _fetch_data(f"https://pokeapi.co/api/v2/type/{pt.type.name}")
            if type_data:
                damage_rel = type_data["damage_relations"]
                
                # Check for past damage relations if available in API (though we use simplified logic here)
                # For Gen 1/2 changes, we can hardcode some or rely on PokeAPI if it supports it well.
                
                for d in damage_rel["double_damage_from"]:
                    if d["name"] in effectiveness:
                        effectiveness[d["name"]] *= 2.0
                for d in damage_rel["half_damage_from"]:
                    if d["name"] in effectiveness:
                        effectiveness[d["name"]] *= 0.5
                for d in damage_rel["no_damage_from"]:
                    if d["name"] in effectiveness:
                        effectiveness[d["name"]] *= 0.0
                
                # Fixes for older generations
                if gen_num < 6:
                    # Before Gen 6, Steel resisted Dark and Ghost
                    if "steel" in effectiveness:
                        # If the Pokemon is Steel, it should resist Dark and Ghost
                        # This logic is slightly wrong because pt.type.name is the Pokemon's type.
                        # We want to know how attacking types affect the Pokemon.
                        pass
                    
                    # If the Pokemon is being attacked by Dark/Ghost and it is Steel
                    if pt.type.name == "steel":
                        if "dark" in effectiveness: effectiveness["dark"] *= 0.5
                        if "ghost" in effectiveness: effectiveness["ghost"] *= 0.5

        # Group by effectiveness
        grouped = defaultdict(list)
        for t, val in effectiveness.items():
            grouped[val].append(t)
            
        def update_ui():
            if not self.pokemon_data: return
            
            # Clear existing effectiveness info
            for child in self.effectiveness_box.get_children():
                self.effectiveness_box.remove(child)
            
            # Define multipliers to show in order
            # 0.0 is Immune, 0.25 is 1/4, 0.5 is 1/2, 1.0 is Neutral, 2.0 is 2x, 4.0 is 4x
            multipliers = [
                (4.0, "4x", "#d32f2f"),
                (2.0, "2x", "#f44336"),
                (1.0, "Neutral", "#757575"),
                (0.5, "1/2", "#4caf50"),
                (0.25, "1/4", "#2e7d32"),
                (0.0, "Immune", "#212121")
            ]
            
            for val, label_text, color_hex in multipliers:
                types_at_val = grouped.get(val, [])
                if not types_at_val:
                    continue
                
                # Frame for each multiplier group to make it a "distinct box"
                frame = Gtk.Frame()
                frame.set_label_align(0.05, 0.5)
                # We'll use the multiplier as the label for the frame
                label_widget = Gtk.Label()
                label_widget.set_markup(f"<span background='{color_hex}' foreground='white' weight='bold'> {label_text} </span>")
                frame.set_label_widget(label_widget)
                
                # Apply CSS to the frame for the colored border
                frame_style_provider = Gtk.CssProvider()
                frame_css = f"frame {{ border: 2px solid {color_hex}; border-radius: 5px; }}"
                frame_style_provider.load_from_data(frame_css.encode('utf-8'))
                frame.get_style_context().add_provider(frame_style_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                
                self.effectiveness_box.pack_start(frame, False, False, 4)

                inner_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                inner_box.set_border_width(6)
                frame.add(inner_box)
                
                # Types FlowBox
                flow = Gtk.FlowBox()
                flow.set_valign(Gtk.Align.CENTER)
                flow.set_max_children_per_line(9) # Increased as they are now in frames
                flow.set_selection_mode(Gtk.SelectionMode.NONE)
                inner_box.pack_start(flow, True, True, 0)
                
                for t in sorted(types_at_val):
                    t_lbl = Gtk.Label()
                    t_color = TYPE_COLORS.get(t.lower(), "#444")
                    t_lbl.set_markup(f"<span background='{t_color}' foreground='white'>  {t.capitalize()}  </span>")
                    flow.add(t_lbl)
            
            self.effectiveness_box.show_all()
        
        GLib.idle_add(update_ui)

    def _render_moves_section(self, parent_box, moves_list, method_id, method_label, gen_name, is_level_up):
        method_title = Gtk.Label()
        method_title.set_markup(f"<b>{method_label}</b>")
        method_title.set_xalign(0)
        parent_box.pack_start(method_title, False, False, 5)

        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_row_spacing(2)
        parent_box.pack_start(grid, False, False, 0)

        headers = ["Lvl", "Move", "Type", "Cat", "Pwr", "Acc"] if is_level_up else ["Move", "Type", "Cat", "Pwr", "Acc"]
        for i, h in enumerate(headers):
            lbl = Gtk.Label(); lbl.set_markup(f"<i>{h}</i>"); lbl.set_xalign(0)
            grid.attach(lbl, i, 0, 1, 1)

        # Sort level-up moves by level
        if is_level_up:
            moves_list.sort(key=lambda x: x.level_learned_at)

        for row_idx, pm in enumerate(moves_list):
            move = pm.move
            r = row_idx + 1
            col = 0
            if is_level_up:
                grid.attach(Gtk.Label(label=str(pm.level_learned_at), xalign=0), col, r, 1, 1); col += 1
            
            grid.attach(Gtk.Label(label=move.name.replace('-',' ').capitalize(), xalign=0), col, r, 1, 1); col += 1
            
            type_color = TYPE_COLORS.get(move.type.name.lower(), "#444")
            type_lbl = Gtk.Label()
            type_lbl.set_markup(f"<span background='{type_color}' foreground='white'> {move.type.name.capitalize()} </span>")
            grid.attach(type_lbl, col, r, 1, 1); col += 1
            
            # Move Category Icon
            cat_icon = Gtk.Image()
            cat_path = CATEGORY_ICONS.get(move.damage_class.lower())
            if cat_path and os.path.exists(cat_path):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(cat_path, 32, 14, True)
                    cat_icon.set_from_pixbuf(pixbuf)
                except Exception as e:
                    print(f"Error loading local icon {cat_path}: {e}")
                    cat_icon.set_from_icon_name("image-missing", Gtk.IconSize.MENU)
            else:
                cat_icon.set_from_icon_name("image-missing", Gtk.IconSize.MENU)
            
            cat_icon.set_tooltip_text(move.damage_class.capitalize())
            grid.attach(cat_icon, col, r, 1, 1); col += 1
            grid.attach(Gtk.Label(label=str(move.power) if move.power else "-", xalign=0), col, r, 1, 1); col += 1
            grid.attach(Gtk.Label(label=str(move.accuracy) if move.accuracy else "-", xalign=0), col, r, 1, 1); col += 1
        
    def _load_evolutions(self, selected_generation):
        if not self.pokemon_data or not self.pokemon_data.evolution_chain_url: return
        evo_data = _fetch_data(self.pokemon_data.evolution_chain_url)
        if not evo_data: return
        
        max_id = GEN_MAX_ID.get(selected_generation, 2000)

        def parse_evolution_details(details, selected_gen_num):
            if not details:
                return ""
            
            # Find the most appropriate evolution detail for the selected generation
            best_detail = None
            for d in details:
                # Basic check: Happiness and Held Items (except Trade) were introduced in Gen 2
                if selected_gen_num < 2:
                    if d.get("min_happiness") or (d.get("held_item") and d.get("trigger", {}).get("name") != "trade"):
                        continue
                
                # Beauty and Move-based evolution introduced in Gen 3/4
                if selected_gen_num < 4:
                    if d.get("known_move") or d.get("known_move_type") or d.get("location"):
                        continue
                
                # Affection/Symmetry/etc in later gens
                if selected_gen_num < 6:
                    if d.get("min_affection"):
                        continue

                best_detail = d
                break
            
            if not best_detail:
                # If no detail matches the gen restrictions (rare in PokeAPI data for base forms),
                # fallback to the first one but it might show "future" methods.
                best_detail = details[0]
                
            d = best_detail
            trigger = d.get("trigger", {}).get("name", "")
            
            parts = []
            if trigger == "level-up":
                if d.get("min_level"):
                    parts.append(f"Lvl {d['min_level']}")
                
                # Generation-gated details
                if selected_gen_num >= 2:
                    if d.get("min_happiness"):
                        parts.append(f"Happiness {d['min_happiness']}")
                
                if selected_gen_num >= 4:
                    if d.get("known_move"):
                        parts.append(f"Move: {d['known_move']['name'].replace('-', ' ').capitalize()}")
                    if d.get("location"):
                        parts.append(f"at {d['location']['name'].replace('-', ' ').capitalize()}")

                if d.get("held_item"):
                    parts.append(f"Holding {d['held_item']['name'].replace('-', ' ').capitalize()}")
                if d.get("time_of_day"):
                    parts.append(f"({d['time_of_day'].capitalize()})")
            elif trigger == "use-item":
                if d.get("item"):
                    parts.append(d["item"]["name"].replace("-", " ").capitalize())
            elif trigger == "trade":
                parts.append("Trade")
                if d.get("held_item"):
                    parts.append(f"holding {d['held_item']['name'].replace('-', ' ').capitalize()}")
            
            if not parts and trigger:
                parts.append(trigger.replace("-", " ").capitalize())
                
            return "\n".join(parts)

        def build_evo_tree(chain, selected_gen_num):
            species_id_str = chain["species"]["url"].split("/")[-2]
            species_id = int(species_id_str)
            
            if species_id > max_id:
                return None

            node = {
                "name": chain["species"]["name"],
                "sprite_url": f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{species_id}.png",
                "details": parse_evolution_details(chain.get("evolution_details", []), selected_gen_num),
                "evolves_to": []
            }
            
            for evolve in chain["evolves_to"]:
                child = build_evo_tree(evolve, selected_gen_num)
                if child:
                    node["evolves_to"].append(child)
            return node
        
        gen_num = int(selected_generation.split(" ")[1])
        evo_tree = build_evo_tree(evo_data["chain"], gen_num)

        def create_pokemon_card(node, img_size, font_size):
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vbox.set_valign(Gtk.Align.CENTER)
            vbox.set_halign(Gtk.Align.CENTER)
            
            frame = Gtk.Frame()
            frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
            
            inner_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            inner_vbox.set_border_width(2)
            frame.add(inner_vbox)
            
            evo_img = Gtk.Image()
            inner_vbox.pack_start(evo_img, False, False, 0)
            
            img_thread = threading.Thread(target=_load_image_in_thread, args=(evo_img, node["sprite_url"], img_size, img_size))
            img_thread.daemon = True
            img_thread.start()
            
            name_lbl = Gtk.Label()
            name_lbl.set_markup(f"<span size='{font_size}'><b>{node['name'].capitalize()}</b></span>")
            inner_vbox.pack_start(name_lbl, False, False, 0)
            
            vbox.pack_start(frame, False, False, 0)
            return vbox

        def render_circular(node, parent_container):
            # Special layout for branching evolutions (like Eevee)
            grid = Gtk.Grid()
            grid.set_column_spacing(20)
            grid.set_row_spacing(20)
            grid.set_halign(Gtk.Align.CENTER)
            grid.set_valign(Gtk.Align.CENTER)
            parent_container.pack_start(grid, True, True, 0)
            
            # Center: The base Pokemon
            base_card = create_pokemon_card(node, 80, "medium")
            grid.attach(base_card, 1, 1, 1, 1)
            
            # Evolutions in a circle around the center
            evos = node["evolves_to"]
            num_evos = len(evos)
            
            # Pre-calculate positions (3x3 grid around center at 1,1)
            # 0,0  1,0  2,0
            # 0,1  BASE 2,1
            # 0,2  1,2  2,2
            positions = [
                (2, 1), (2, 2), (1, 2), (0, 2), (0, 1), (0, 0), (1, 0), (2, 0)
            ]
            
            for i, evo in enumerate(evos):
                if i >= len(positions): break # Limit to 8 for symmetry, though Eevee has exactly 8
                
                pos_x, pos_y = positions[i]
                
                evo_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                
                # Details above or below depending on position
                details_text = evo["details"].replace('\n', ' ')
                if details_text:
                    details_lbl = Gtk.Label()
                    details_lbl.set_markup(f"<span size='x-small' color='#888'>{details_text}</span>")
                    details_lbl.set_max_width_chars(15)
                    details_lbl.set_line_wrap(True)
                    if pos_y == 0: # Top row, put details above
                        evo_vbox.pack_start(details_lbl, False, False, 0)
                    
                card = create_pokemon_card(evo, 64, "small")
                evo_vbox.pack_start(card, False, False, 0)
                
                if details_text and pos_y != 0: # Not top row, put details below
                    evo_vbox.pack_start(details_lbl, False, False, 0)
                    
                grid.attach(evo_vbox, pos_x, pos_y, 1, 1)

        def render_tree(node, parent_container):
            # Use circular layout if there are many branches at this level
            if len(node["evolves_to"]) > 2:
                render_circular(node, parent_container)
                return

            # Normal linear/small branch layout
            stage_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            stage_hbox.set_halign(Gtk.Align.CENTER)
            parent_container.pack_start(stage_hbox, False, False, 0)
            
            card = create_pokemon_card(node, 80, "medium")
            stage_hbox.pack_start(card, False, False, 0)
            
            if node["evolves_to"]:
                evolutions_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
                stage_hbox.pack_start(evolutions_column, False, False, 0)
                
                for evo in node["evolves_to"]:
                    evo_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                    evolutions_column.pack_start(evo_row, False, False, 0)
                    
                    arrow_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                    arrow_box.set_valign(Gtk.Align.CENTER)
                    
                    if evo["details"]:
                        details_lbl = Gtk.Label()
                        details_lbl.set_markup(f"<span size='x-small' color='#888'>{evo['details']}</span>")
                        details_lbl.set_justify(Gtk.Justification.CENTER)
                        details_lbl.set_line_wrap(True)
                        details_lbl.set_max_width_chars(15)
                        arrow_box.pack_start(details_lbl, False, False, 0)
                    
                    arrow = Gtk.Label(label="➔")
                    arrow_box.pack_start(arrow, False, False, 0)
                    evo_row.pack_start(arrow_box, False, False, 0)
                    
                    render_tree(evo, evo_row)

        def update_ui():
            if not self.pokemon_data or not evo_tree: return
            
            for child in self.evo_box.get_children():
                self.evo_box.remove(child)
                
            render_tree(evo_tree, self.evo_box)
            
            self.evo_box.show_all()
            self.main_box.thaw_child_notify()

        GLib.idle_add(update_ui)

    def _load_varieties(self, species_url):
        varieties = get_species_varieties(species_url)
        if not varieties or len(varieties) <= 1:
            GLib.idle_add(lambda: self.forms_scroll.hide())
            GLib.idle_add(lambda: self.forms_tab_label.hide())
            return
        else:
            GLib.idle_add(lambda: self.forms_scroll.show())
            GLib.idle_add(lambda: self.forms_tab_label.show())

        def on_variety_clicked(button, pokemon_id):
            from ..data.database import get_session, update_pokemon_data
            session = get_session()
            pokemon = session.query(Pokemon).filter_by(id=pokemon_id).first()
            if not pokemon:
                pokemon = update_pokemon_data(session, pokemon_id)
            session.close()
            if pokemon:
                GLib.idle_add(self.update_data, pokemon)

        def update_ui():
            for child in self.varieties_box.get_children():
                self.varieties_box.remove(child)

            flow = Gtk.FlowBox()
            flow.set_selection_mode(Gtk.SelectionMode.NONE)
            flow.set_max_children_per_line(5)
            self.varieties_box.pack_start(flow, True, True, 0)

            for variety in varieties:
                p_url = variety["pokemon"]["url"]
                p_id = int(p_url.split("/")[-2])
                p_name = variety["pokemon"]["name"]
                
                # Derive form display name
                species_name = self.pokemon_data.species_url.split("/")[-2]
                # Sometimes species_url is a full name, sometimes ID. PokeAPI results vary.
                # Let's use a simpler heuristic: variety name vs base name
                # Actually we can just use the variety name and capitalize it
                
                btn = Gtk.Button()
                btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                btn.add(btn_box)
                
                v_img = Gtk.Image()
                btn_box.pack_start(v_img, False, False, 0)
                sprite_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{p_id}.png"
                threading.Thread(target=_load_image_in_thread, args=(v_img, sprite_url, 48, 48)).start()
                
                # Try to make label short
                display_name = p_name.capitalize()
                if "-" in p_name:
                    parts = p_name.split("-")
                    if len(parts) > 1:
                        display_name = parts[-1].capitalize()

                lbl = Gtk.Label(label=display_name)
                lbl.set_ellipsize(Pango.EllipsizeMode.END)
                lbl.set_max_width_chars(10)
                btn_box.pack_start(lbl, False, False, 0)
                
                btn.connect("clicked", on_variety_clicked, p_id)
                btn.set_tooltip_text(p_name.replace("-", " ").capitalize())
                
                if p_id == self.pokemon_data.id:
                    btn.set_sensitive(False)
                    btn.get_style_context().add_class("suggested-action")

                flow.add(btn)
            self.varieties_box.show_all()

        GLib.idle_add(update_ui)
