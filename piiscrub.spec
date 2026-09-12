# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec. Bundles the spaCy model so the app works fully offline."""
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for pkg in ("en_core_web_lg", "spacy", "thinc", "presidio_analyzer", "blis",
            "tldextract", "srsly", "cymem", "preshed", "murmurhash", "catalogue", "wasabi",
            "customtkinter", "darkdetect"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["tkinter", "pypdf"],
    hookspath=[],
    excludes=["matplotlib", "PyQt5", "PySide2", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="PII Scrub",
    console=False,
    argv_emulation=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="PII Scrub")
app = BUNDLE(
    coll,
    name="PII Scrub.app",
    bundle_identifier="app.piiscrub.desktop",
    info_plist={"NSHighResolutionCapable": True, "LSMinimumSystemVersion": "13.0"},
)
