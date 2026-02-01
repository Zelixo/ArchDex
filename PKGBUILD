pkgname=archdex
pkgver=0.1.0
pkgrel=1
pkgdesc="A Pokedex application for aarch64 Linux with Hyprland"
arch=('aarch64' 'x86_64')
url="https://github.com/Zelixo/ArchDex"
license=('MIT')
depends=('python' 'gtk3' 'python-gobject' 'python-requests' 'python-notify2' 'python-dbus' 'python-sqlalchemy')
makedepends=('python-build' 'python-installer' 'python-setuptools' 'python-wheel')
source=("archdex-$pkgver.tar.gz::https://github.com/Zelixo/ArchDex/archive/v$pkgver.tar.gz")
sha256sums=('SKIP') # Replace with actual hash when releasing

build() {
  cd "ArchDex-$pkgver"
  python -m build --wheel --no-isolation
}

package() {
  cd "ArchDex-$pkgver"
  python -m installer --destdir="$pkgdir" dist/*.whl
  
  # Install desktop file and icons if we had them
  # install -Dm644 assets/archdex.desktop "$pkgdir/usr/share/applications/archdex.desktop"
  # install -Dm644 assets/icons/archdex.png "$pkgdir/usr/share/pixmaps/archdex.png"
}
