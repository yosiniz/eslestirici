#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCH="${PACKAGE_ARCH:-$(uname -m)}"
DIST_DIR="$PROJECT_ROOT/dist-macos"
WORK_DIR="$PROJECT_ROOT/build-macos"
RELEASE_DIR="$PROJECT_ROOT/release"
STAGING_DIR="$WORK_DIR/dmg-root"
APP_PATH="$DIST_DIR/Otopark Plaka Kontrol.app"
DMG_PATH="$RELEASE_DIR/OtoparkPlakaKontrol-macOS-${ARCH}.dmg"

cd "$PROJECT_ROOT"

HOST_ARCH="$(uname -m)"
if [[ "$ARCH" != "arm64" && "$ARCH" != "x86_64" ]]; then
  echo "Desteklenmeyen macOS mimarisi: $ARCH" >&2
  exit 1
fi
if [[ "$ARCH" != "$HOST_ARCH" ]]; then
  echo "İstenen mimari ($ARCH), çalışan Mac mimarisiyle ($HOST_ARCH) aynı olmalıdır." >&2
  exit 1
fi

python -m unittest discover -s tests -v
python -m PyInstaller \
  --noconfirm \
  --clean \
  --distpath "$DIST_DIR" \
  --workpath "$WORK_DIR/pyinstaller" \
  OtoparkPlakaKontrol-macOS.spec

if [[ ! -d "$APP_PATH" ]]; then
  echo "Uygulama paketi bulunamadı: $APP_PATH" >&2
  exit 1
fi

if [[ -n "${MACOS_SIGNING_IDENTITY:-}" ]]; then
  codesign --force --deep --options runtime \
    --sign "$MACOS_SIGNING_IDENTITY" "$APP_PATH"
else
  echo "MACOS_SIGNING_IDENTITY tanımlı değil; uygulama ad-hoc imzalanıyor."
  codesign --force --deep --sign - "$APP_PATH"
fi

codesign --verify --deep --strict --verbose=2 "$APP_PATH"

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR" "$RELEASE_DIR"
cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"
rm -f "$DMG_PATH"
hdiutil create \
  -volname "Otopark Plaka Kontrol" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "macOS DMG hazır: $DMG_PATH"
