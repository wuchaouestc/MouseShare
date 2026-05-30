# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

bleak_hiddenimports = collect_submodules('bleak')
winrt_hiddenimports = []
for package in ('winrt', 'winrt.windows.devices.bluetooth', 'winrt.windows.devices.enumeration', 'winrt.windows.storage.streams'):
    try:
        winrt_hiddenimports += collect_submodules(package)
    except Exception:
        pass

bleak_datas = []
for package in ('bleak', 'winrt-runtime', 'winrt-Windows.Devices.Bluetooth', 'winrt-Windows.Devices.Enumeration', 'winrt-Windows.Storage.Streams'):
    try:
        bleak_datas += copy_metadata(package)
    except Exception:
        pass


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')] + bleak_datas,
    hiddenimports=['PySide6.QtCore', 'PySide6.QtWidgets', 'PySide6.QtGui', 'pynput.mouse', 'pynput._util', 'src.shared.protocol', 'src.shared.transport', 'src.shared.config', 'src.shared.state_machine', 'src.shared.bluetooth_scanner', 'src.shared.peer_agent', 'src.host.input_capture', 'src.host.boundary_engine', 'src.host.cursor_controller', 'src.host.state_machine', 'src.target.rfcomm_server', 'src.target.input_injector', 'src.target.state_machine', 'src.ui.main_window', 'src.ui.device_list', 'src.ui.layout_config', 'src.ui.status_page', 'src.ui.tray'] + bleak_hiddenimports + winrt_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MouseShare',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
