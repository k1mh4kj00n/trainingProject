# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for physical_analysis (Kubios-style HRV + NIRS-VOT GUI).

빌드:
    pyinstaller build_exe.spec --noconfirm

산출물 (one-file 모드):
    Windows: dist/physical_analysis.exe   (단일 파일)
    Linux:   dist/physical_analysis       (단일 ELF)

주의:
    --onefile은 PySide6+scipy+matplotlib DLL을 .exe 안에 압축해 두고,
    실행할 때마다 %TEMP%\\_MEIxxxxxx\\ 로 풀어 거기서 로드한다.
    → 첫 시작 5~10초 지연, 디스크에 임시 파일 생성, 일부 백신이 의심.
    빠른 실행이 필요하면 COLLECT 블록 살리고 EXE의 exclude_binaries=True 로 되돌릴 것.
"""

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# matplotlib Qt backend는 동적 import라 명시 필요.
hiddenimports = [
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_qt5agg",
]
hiddenimports += collect_submodules("hrv_analysis")
hiddenimports += collect_submodules("nirs_vot")
hiddenimports += collect_submodules("nirs_vot_gui")
# SciPy 1.15+ 의 array_api_compat 가 동적 import를 쓰는데
# (scipy._lib.array_api_compat.numpy.fft 등) PyInstaller 자동 탐지 누락.
# 통째로 끌어와서 안전하게 처리.
hiddenimports += collect_submodules("scipy")
hiddenimports += collect_submodules("numpy")

# 사용 안 하는 큰 패키지 제외 — 산출물 사이즈와 빌드 시간 절약
excludes = [
    "tkinter",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "sphinx",
    "pyqtgraph",
]

a = Analysis(
    ["run_app.py"],
    pathex=["scripts"],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="physical_analysis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,       # %TEMP% 기본값 사용
    console=False,             # GUI 앱 — 콘솔창 없이
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
