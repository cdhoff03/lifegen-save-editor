# PyInstaller spec for lifegen-save-editor.
#
# Build:   pyinstaller --clean packaging/lifegen-save-editor.spec
# Output:  dist/lifegen-save-editor/  (or .app bundle on macOS)
#
# This file works on Windows, macOS, and Linux. PyInstaller's PySide6 hook
# bundles the Qt plugins automatically.
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent
APP_NAME = "lifegen-save-editor"

datas = [
    (str(ROOT / "assets"), "assets"),
]

block_cipher = None

a = Analysis(
    [str(ROOT / "lifegen_editor" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("lifegen_editor"),
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "test", "unittest"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

# macOS: wrap into an .app bundle as well as the COLLECT directory.
import sys
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        bundle_identifier="app.lifegen.saveeditor",
        info_plist={
            "CFBundleName": "LifeGen Save Editor",
            "CFBundleDisplayName": "LifeGen Save Editor",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
