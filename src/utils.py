import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib, Gio
import requests
from io import BytesIO
import threading
import os
import hashlib
from concurrent.futures import ThreadPoolExecutor

CACHE_DIR = os.path.expanduser("~/.cache/archdex/images")
image_executor = ThreadPoolExecutor(max_workers=4)

def get_cache_path(url):
    if not url:
        return None
    hashed_url = hashlib.md5(url.encode()).hexdigest()
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, hashed_url)

def _load_image_in_thread(image_widget, url, width, height):
    if not url:
        print("Warning: No URL provided for image loading.")
        GLib.idle_add(image_widget.set_from_icon_name, "image-missing", Gtk.IconSize.DIALOG)
        return
    try:
        cache_path = get_cache_path(url)
        if cache_path and os.path.exists(cache_path):
            with open(cache_path, "rb") as f:
                image_data = f.read()
        else:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image_data = response.content
            if cache_path:
                with open(cache_path, "wb") as f:
                    f.write(image_data)

        bytes_io = BytesIO(image_data)
        input_stream = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(bytes_io.read()))
        pixbuf = GdkPixbuf.Pixbuf.new_from_stream(input_stream, None)
        scaled_pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        GLib.idle_add(image_widget.set_from_pixbuf, scaled_pixbuf)
    except (requests.exceptions.RequestException, IOError) as e:
        print(f"Error loading image from {url}: {e}")
        GLib.idle_add(image_widget.set_from_icon_name, "image-missing", Gtk.IconSize.MENU)
    except Exception as e:
        print(f"Error processing image: {e}")
        GLib.idle_add(image_widget.set_from_icon_name, "image-missing", Gtk.IconSize.MENU)

