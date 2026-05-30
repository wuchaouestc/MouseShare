import ctypes
import logging
from ctypes import wintypes

logger = logging.getLogger(__name__)

MAJOR_CLASS_MISC = 0x00
MAJOR_CLASS_COMPUTER = 0x01
MAJOR_CLASS_PHONE = 0x02
MAJOR_CLASS_LAN = 0x03
MAJOR_CLASS_AUDIO = 0x04
MAJOR_CLASS_PERIPHERAL = 0x05
MAJOR_CLASS_IMAGING = 0x06
MAJOR_CLASS_WEARABLE = 0x07
MAJOR_CLASS_TOY = 0x08
MAJOR_CLASS_HEALTH = 0x09

NON_COMPUTER_MAJOR_CLASSES = {
    MAJOR_CLASS_PHONE,
    MAJOR_CLASS_AUDIO,
    MAJOR_CLASS_PERIPHERAL,
    MAJOR_CLASS_IMAGING,
    MAJOR_CLASS_WEARABLE,
    MAJOR_CLASS_TOY,
    MAJOR_CLASS_HEALTH,
}


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


def set_discoverable(enable: bool) -> bool:
    """设置本机蓝牙可被发现状态。返回是否成功。"""
    bthprops = _load_bthprops()
    if bthprops is None:
        return False
    try:
        bthprops.BluetoothEnableDiscovery.argtypes = [wintypes.HANDLE, wintypes.BOOL]
        bthprops.BluetoothEnableDiscovery.restype = wintypes.BOOL
        result = bthprops.BluetoothEnableDiscovery(None, bool(enable))
        logger.info("蓝牙可发现状态设置为 %s，结果=%s", enable, result)
        return bool(result)
    except Exception as e:
        logger.warning("设置蓝牙可发现状态失败: %s", e)
        return False


class BLUETOOTH_OOB_DATA_INFO(ctypes.Structure):
    _fields_ = [("C", ctypes.c_byte * 16), ("R", ctypes.c_byte * 16)]


def pair_device(address: str) -> tuple:
    """对指定 MAC 地址的设备发起配对。
    返回 (success: bool, error_msg: str)
    """
    bthprops = _load_bthprops()
    if bthprops is None:
        return False, "无法加载蓝牙 API"

    # 先找到设备信息
    bthprops.BluetoothFindFirstDevice.argtypes = [
        ctypes.POINTER(BLUETOOTH_DEVICE_SEARCH_PARAMS),
        ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
    ]
    bthprops.BluetoothFindFirstDevice.restype = HBLUETOOTH_DEVICE_FIND
    bthprops.BluetoothFindNextDevice.argtypes = [
        HBLUETOOTH_DEVICE_FIND, ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
    ]
    bthprops.BluetoothFindNextDevice.restype = wintypes.BOOL
    bthprops.BluetoothFindDeviceClose.argtypes = [HBLUETOOTH_DEVICE_FIND]
    bthprops.BluetoothFindDeviceClose.restype = wintypes.BOOL

    # 将 MAC 字符串转为整数
    target_addr = 0
    for p in address.replace("-", ":").split(":"):
        target_addr = (target_addr << 8) | int(p, 16)

    search_params = BLUETOOTH_DEVICE_SEARCH_PARAMS()
    search_params.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS)
    search_params.fReturnAuthenticated = True
    search_params.fReturnRemembered = True
    search_params.fReturnUnknown = True
    search_params.fReturnConnected = True
    search_params.fIssueInquiry = True
    search_params.cTimeoutMultiplier = 8
    search_params.hRadio = None

    device_info = BLUETOOTH_DEVICE_INFO()
    device_info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)

    found_info = None
    hFind = bthprops.BluetoothFindFirstDevice(
        ctypes.byref(search_params), ctypes.byref(device_info)
    )
    if hFind:
        try:
            while True:
                if int(device_info.Address) == target_addr:
                    found_info = BLUETOOTH_DEVICE_INFO()
                    ctypes.memmove(
                        ctypes.byref(found_info),
                        ctypes.byref(device_info),
                        ctypes.sizeof(BLUETOOTH_DEVICE_INFO),
                    )
                    break
                if not bthprops.BluetoothFindNextDevice(hFind, ctypes.byref(device_info)):
                    break
        finally:
            bthprops.BluetoothFindDeviceClose(hFind)

    if found_info is None:
        # 设备未在扫描列表中，构造一个最小 BLUETOOTH_DEVICE_INFO
        found_info = BLUETOOTH_DEVICE_INFO()
        found_info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)
        found_info.Address = target_addr

    if bool(found_info.fAuthenticated):
        return True, "已配对"

    try:
        bthprops.BluetoothAuthenticateDeviceEx.argtypes = [
            wintypes.HWND,
            wintypes.HANDLE,
            ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
            ctypes.POINTER(BLUETOOTH_OOB_DATA_INFO),
            ctypes.c_int,  # AUTHENTICATION_REQUIREMENTS
        ]
        bthprops.BluetoothAuthenticateDeviceEx.restype = wintypes.DWORD
        # MITMProtectionNotRequired = 0
        ret = bthprops.BluetoothAuthenticateDeviceEx(
            None, None, ctypes.byref(found_info), None, 0
        )
        if ret == 0:
            return True, "配对成功"
        else:
            return False, f"配对失败，错误码: {ret}"
    except Exception as e:
        return False, str(e)


def get_windows_bluetooth_devices(
    only_computers: bool = True,
    issue_inquiry: bool = True,
    timeout_multiplier: int = 8,
):
    """枚举 Windows 蓝牙设备。

    only_computers=True 时返回 Major Class=Computer 的设备，以及 Misc(0x00)/
    Uncategorized(0x1F) 等无法明确归类、但实际可能是电脑的设备；明确属于手机/
    音频/外设/可穿戴等类别的会被过滤掉。
    issue_inquiry=True 时主动发起一次蓝牙询问以发现未配对的可见设备。
    timeout_multiplier 单位约为 1.28 秒，Windows 取值范围 1~48。默认 8 ≈ 10 秒，
    比之前的 4 (~5 秒) 更稳，能覆盖回包较慢的设备。
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

    clamped_timeout = max(1, min(48, int(timeout_multiplier)))
    search_params = BLUETOOTH_DEVICE_SEARCH_PARAMS()
    search_params.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS)
    search_params.fReturnAuthenticated = True
    search_params.fReturnRemembered = True
    search_params.fReturnUnknown = True
    search_params.fReturnConnected = True
    search_params.fIssueInquiry = bool(issue_inquiry)
    search_params.cTimeoutMultiplier = clamped_timeout
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
            if (not only_computers) or major not in NON_COMPUTER_MAJOR_CLASSES:
                devices.append(entry)
            else:
                logger.debug(
                    "忽略非电脑设备 name=%s mac=%s major=0x%02X cod=0x%06X",
                    name, mac, major, cod,
                )

            if not bthprops.BluetoothFindNextDevice(hFind, ctypes.byref(device_info)):
                break
    finally:
        bthprops.BluetoothFindDeviceClose(hFind)

    return devices
