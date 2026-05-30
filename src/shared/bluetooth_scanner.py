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


_WINERR = {
    0x4E3:  "操作已取消（用户拒绝配对）",
    0x4E6:  "配对请求超时",
    0x4E7:  "设备不在范围内或未响应",
    0x4E9:  "配对被对端拒绝",
    0x4EA:  "配对已在进行中",
    0x4EB:  "设备不支持此配对方式",
    0x4EC:  "配对失败（认证错误）",
    0x4ED:  "配对失败（连接错误）",
    0x4EE:  "配对失败（加密错误）",
    0x4EF:  "配对失败（设备不可达）",
    0x4F0:  "配对失败（无效参数）",
    0x4F1:  "配对失败（资源不足）",
    0x4F2:  "配对失败（不支持的功能）",
    0x5:    "拒绝访问（需要管理员权限）",
    0x57:   "参数无效",
    0x3E3:  "操作被中断",
}


def _win_error_str(code: int) -> str:
    if code in _WINERR:
        return f"{_WINERR[code]} (0x{code:X})"
    # 尝试从系统获取描述
    try:
        import ctypes as _c
        buf = _c.create_unicode_buffer(512)
        _c.windll.kernel32.FormatMessageW(
            0x1000 | 0x200, None, code, 0, buf, 512, None
        )
        desc = buf.value.strip()
        if desc:
            return f"{desc} (0x{code:X})"
    except Exception:
        pass
    return f"错误码 0x{code:X}"


def _find_device_info(bthprops, target_addr: int):
    """在已知设备列表中查找指定地址的 BLUETOOTH_DEVICE_INFO，找不到返回 None。"""
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

    search_params = BLUETOOTH_DEVICE_SEARCH_PARAMS()
    search_params.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS)
    search_params.fReturnAuthenticated = True
    search_params.fReturnRemembered = True
    search_params.fReturnUnknown = True
    search_params.fReturnConnected = True
    search_params.fIssueInquiry = False  # 不重新扫描，只查已知列表
    search_params.cTimeoutMultiplier = 1
    search_params.hRadio = None

    device_info = BLUETOOTH_DEVICE_INFO()
    device_info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)

    hFind = bthprops.BluetoothFindFirstDevice(
        ctypes.byref(search_params), ctypes.byref(device_info)
    )
    if not hFind:
        return None
    try:
        while True:
            if int(device_info.Address) == target_addr:
                copy = BLUETOOTH_DEVICE_INFO()
                ctypes.memmove(
                    ctypes.byref(copy), ctypes.byref(device_info),
                    ctypes.sizeof(BLUETOOTH_DEVICE_INFO),
                )
                return copy
            if not bthprops.BluetoothFindNextDevice(hFind, ctypes.byref(device_info)):
                return None
    finally:
        bthprops.BluetoothFindDeviceClose(hFind)


def pair_device(address: str) -> tuple:
    """对指定 MAC 地址的设备发起配对。返回 (success: bool, error_msg: str)。"""
    import time

    bthprops = _load_bthprops()
    if bthprops is None:
        return False, "无法加载蓝牙 API（bthprops.cpl）"

    target_addr = 0
    for p in address.replace("-", ":").split(":"):
        target_addr = (target_addr << 8) | int(p, 16)

    # 查找设备信息（不发起新扫描，用已缓存的）
    found_info = _find_device_info(bthprops, target_addr)

    if found_info is not None and bool(found_info.fAuthenticated):
        return True, "已配对"

    # 若设备不在列表中，构造最小结构（BluetoothAuthenticateDeviceEx 仍可工作）
    if found_info is None:
        logger.warning("pair_device: 设备 %s 不在已知列表，尝试直接配对", address)
        found_info = BLUETOOTH_DEVICE_INFO()
        found_info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)
        found_info.Address = target_addr

    try:
        bthprops.BluetoothAuthenticateDeviceEx.argtypes = [
            wintypes.HWND,
            wintypes.HANDLE,
            ctypes.POINTER(BLUETOOTH_DEVICE_INFO),
            ctypes.POINTER(BLUETOOTH_OOB_DATA_INFO),
            ctypes.c_int,
        ]
        bthprops.BluetoothAuthenticateDeviceEx.restype = wintypes.DWORD
        # MITMProtectionNotRequired=0，Just Works / Numeric Comparison 由系统决定
        ret = bthprops.BluetoothAuthenticateDeviceEx(
            None, None, ctypes.byref(found_info), None, 0
        )
        logger.info("BluetoothAuthenticateDeviceEx ret=0x%X for %s", ret, address)
        if ret == 0:
            # 等待系统完成配对状态写入，再继续连接
            time.sleep(1.5)
            return True, "配对成功"
        else:
            return False, f"配对失败：{_win_error_str(ret)}"
    except Exception as e:
        return False, f"配对异常：{e}"


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
