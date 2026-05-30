import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

MAJOR_CLASS_MISC = 0x00
MAJOR_CLASS_COMPUTER = 0x01
MAJOR_CLASS_PHONE = 0x02
MAJOR_CLASS_AUDIO = 0x04
MAJOR_CLASS_PERIPHERAL = 0x05


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
    ]


class BLUETOOTH_DEVICE_SEARCH_PARAMS(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("fReturnAuthenticated", wintypes.BOOL),
        ("fReturnRemembered", wintypes.BOOL),
        ("fReturnUnknown", wintypes.BOOL),
        ("fReturnConnected", wintypes.BOOL),
        ("fIssueInquiry", wintypes.BOOL),
        ("cTimeoutMultiplier", ctypes.c_ubyte),
        ("hRadio", wintypes.HANDLE),
    ]


class BLUETOOTH_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("Address", ctypes.c_ulonglong),
        ("ulClassofDevice", wintypes.ULONG),
        ("fConnected", wintypes.BOOL),
        ("fRemembered", wintypes.BOOL),
        ("fAuthenticated", wintypes.BOOL),
        ("stLastSeen", SYSTEMTIME),
        ("stLastUsed", SYSTEMTIME),
        ("szName", wintypes.WCHAR * 248),
    ]


HBLUETOOTH_DEVICE_FIND = wintypes.HANDLE


def _major_class(cod: int) -> int:
    return (cod >> 8) & 0x1F


def _format_mac(addr: int) -> str:
    return ":".join(f"{(addr >> (8 * i)) & 0xFF:02X}" for i in range(5, -1, -1))


def _load_bthprops():
    for name in ("bthprops.cpl", "BluetoothAPIs.dll"):
        try:
            return ctypes.WinDLL(name)
        except OSError:
            continue
    return None


def get_windows_bluetooth_devices(only_computers: bool = True, issue_inquiry: bool = True):
    """枚举 Windows 蓝牙设备。

    only_computers=True 时仅返回 Major Class=Computer 的设备（即周围的 Windows/PC 电脑）。
    issue_inquiry=True 时主动发起一次蓝牙询问以发现未配对的可见设备。
    """
    bthprops = _load_bthprops()
    if bthprops is None:
        logger.warning("无法加载 Windows 蓝牙 API（bthprops.cpl / BluetoothAPIs.dll）")
        return []

    bthprops.BluetoothFindFirstDevice.argtypes = [
        ctypes.POINTER(BLUETOOTH_DEVICE_SEARCH_PARAMS),
        ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
    ]
    bthprops.BluetoothFindFirstDevice.restype = HBLUETOOTH_DEVICE_FIND

    bthprops.BluetoothFindNextDevice.argtypes = [
        HBLUETOOTH_DEVICE_FIND,
        ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
    ]
    bthprops.BluetoothFindNextDevice.restype = wintypes.BOOL

    bthprops.BluetoothFindDeviceClose.argtypes = [HBLUETOOTH_DEVICE_FIND]
    bthprops.BluetoothFindDeviceClose.restype = wintypes.BOOL

    search_params = BLUETOOTH_DEVICE_SEARCH_PARAMS()
    search_params.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS)
    search_params.fReturnAuthenticated = True
    search_params.fReturnRemembered = True
    search_params.fReturnUnknown = True
    search_params.fReturnConnected = True
    search_params.fIssueInquiry = bool(issue_inquiry)
    search_params.cTimeoutMultiplier = 4
    search_params.hRadio = None

    device_info = BLUETOOTH_DEVICE_INFO()
    device_info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)

    devices = []
    hFind = bthprops.BluetoothFindFirstDevice(
        ctypes.byref(search_params), ctypes.byref(device_info)
    )
    if not hFind:
        logger.info("BluetoothFindFirstDevice 未返回任何设备")
        return devices

    try:
        while True:
            cod = int(device_info.ulClassofDevice)
            major = _major_class(cod)
            mac = _format_mac(int(device_info.Address))
            name = device_info.szName or ""
            entry = {
                "name": name,
                "address": mac,
                "class_of_device": cod,
                "major_class": major,
                "authenticated": bool(device_info.fAuthenticated),
                "remembered": bool(device_info.fRemembered),
                "connected": bool(device_info.fConnected),
            }
            if (not only_computers) or major == MAJOR_CLASS_COMPUTER:
                devices.append(entry)

            if not bthprops.BluetoothFindNextDevice(hFind, ctypes.byref(device_info)):
                break
    finally:
        bthprops.BluetoothFindDeviceClose(hFind)

    return devices
