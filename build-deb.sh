#!/bin/sh
# Build keyscreen_<version>_all.deb into ./dist
set -e
cd "$(dirname "$0")"
VERSION=$(sed -n 's/^Version: //p' packaging/DEBIAN/control)
B=$(mktemp -d)
mkdir -p "$B/DEBIAN" "$B/usr/bin" "$B/usr/share/applications" dist
install -m 644 packaging/DEBIAN/control "$B/DEBIAN/control"
install -m 755 packaging/DEBIAN/postinst "$B/DEBIAN/postinst"
install -m 755 keyscreen keyscreen-toggle "$B/usr/bin/"
install -m 644 keyscreen.desktop "$B/usr/share/applications/"
chmod 755 "$B" "$B/usr" "$B/usr/bin" "$B/usr/share" "$B/usr/share/applications"
dpkg-deb --root-owner-group --build "$B" "dist/keyscreen_${VERSION}_all.deb"
rm -rf "$B"
echo "Built dist/keyscreen_${VERSION}_all.deb"
