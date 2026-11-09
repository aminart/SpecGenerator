# PyInstaller recipe for SpecGenerator.exe (run build_exe.bat, or see README).
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Version: the VERSION file (single source), bundled with the app and shown in the exe's
# Properties > Details on Windows (that version resource needs PyInstaller's Windows modules).
VERSION = Path("VERSION").read_text(encoding="utf-8").strip()
try:
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
    )
except ImportError:  # not on Windows: no version resource, the build goes on
    version_info = None
else:
    _numbers = tuple(int(part) for part in VERSION.split("-")[0].split(".")) + (0,)
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=_numbers[:4], prodvers=_numbers[:4]),
        kids=[
            StringFileInfo([StringTable("040C04B0", [
                StringStruct("ProductName", "SpecGen"),
                StringStruct("FileDescription", "SpecGen - générateur de documents UX"),
                StringStruct("ProductVersion", VERSION),
                StringStruct("FileVersion", VERSION),
                StringStruct("OriginalFilename", "SpecGenerator.exe"),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x040C, 1200])]),
        ],
    )

datas = [
    ("backend/Template_Documentatio_Specs_fr.docx", "."),
    ("backend/Template_Documentatio_Specs_en.docx", "."),
    ("backend/Template_Documentatio_Context_fr.docx", "."),
    ("backend/Template_Documentatio_Context_en.docx", "."),
    ("frontend/dist", "frontend_dist"),
    ("VERSION", "."),
]
binaries = []
hiddenimports = collect_submodules("uvicorn")

# MarkItDown converters and the libraries they read documents with (data files included).
# Left out on purpose (tens of MB): Magika + onnxruntime (MarkItDown's file-type sniffing, unused: the type comes
# from the extension), pandas + numpy (replaced by openpyxl for Excel); see backend/markdown_converter.py.
for package in ("markitdown", "pdfminer", "pdfplumber", "pptx", "docx", "mammoth", "openpyxl"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    ["backend/launcher.py"],
    pathex=["backend"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "magika", "onnxruntime", "pandas", "numpy",
              "watchfiles", "uvloop", "pypdfium2", "pypdfium2_raw", "yaml"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SpecGenerator",
    icon=os.path.join(SPECPATH, "icone", "specgen.ico"),
    version=version_info,
    console=True,
    upx=False,
)
