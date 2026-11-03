# PyInstaller recipe for SpecGenerator.exe (run build_exe.bat, or see README).
from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [
    ("backend/Template_Documentatio_Specs_fr.docx", "."),
    ("backend/Template_Documentatio_Specs_en.docx", "."),
    ("backend/Template_Documentatio_Context_fr.docx", "."),
    ("backend/Template_Documentatio_Context_en.docx", "."),
    ("frontend/dist", "frontend_dist"),
]
binaries = []
hiddenimports = collect_submodules("uvicorn")

# MarkItDown and its file-type detection (magika, onnxruntime) ship data files and models.
for package in ("markitdown", "magika", "onnxruntime", "pdfminer", "pptx", "docx", "mammoth", "openpyxl"):
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
    excludes=["tkinter", "matplotlib", "IPython"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SpecGenerator",
    console=True,
    upx=False,
)
