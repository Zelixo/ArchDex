import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

def load_css(css_file_path=None):
    """Loads a custom CSS file for the GTK application. If None, relies on system theme."""
    css_provider = Gtk.CssProvider()
    try:
        if css_file_path:
            css_provider.load_from_path(css_file_path)
            print(f"Loaded custom CSS from: {css_file_path}")
        else:
            # Attempt to load default GTK theme from system
            # This is largely automatic for GTK applications in Wayland/Hyprland
            print("Relying on system GTK theme configuration.")

        settings = Gtk.Settings.get_default()
        if settings:
            # Access properties directly
            dark_theme_preferred = settings.props.gtk_application_prefer_dark_theme
            print(f"Dark theme preferred by system: {dark_theme_preferred}")

        screen = Gdk.Screen.get_default()
        if screen:
            Gtk.StyleContext.add_provider_for_screen(
                screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
    except Exception as e:
        print(f"Error loading CSS or checking theme settings: {e}")
