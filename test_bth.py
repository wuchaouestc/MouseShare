import ctypes
from ctypes import wintypes

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

def get_bluetooth_devices():
    try:
        bthprops = ctypes.WinDLL("bthprops.cpl")
    except OSError:
        try:
            bthprops = ctypes.WinDLL("BluetoothAPIs.dll")
        except OSError:
            return []

    search_params = BLUETOOTH_DEVICE_SEARCH_PARAMS()
    search_params.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS)
    search_params.fReturnAuthenticated = True
    search_params.fReturnRemembered = True
    search_params.fReturnUnknown = False
    search_params.fReturnConnected = True
    search_params.fIssueInquiry = False  # Try to discover
    search_params.cTimeoutMultiplier = 2
    search_params.hRadio = None

    device_info = BLUETOOTH_DEVICE_INFO()
    device_info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)

    devices = []
    
    hFind = bthprops.BluetoothFindFirstDevice(ctypes.byref(search_params), ctypes.byref(device_info))
    if not hFind:
        return devices

    while True:
        addr = device_info.Address
        mac_address = f"{(addr >> 40) & 0xFF:02X}:{(addr >> 32) & 0xFF:02X}:{(addr >> 24) & 0xFF:02X}:{(addr >> 16) & 0xFF:02X}:{(addr >> 8) & 0xFF:02X}:{addr & 0xFF:02X}"
        name = device_info.szName
        devices.append({"name": name, "address": mac_address})
        
        if not bthprops.BluetoothFindNextDevice(hFind, ctypes.byref(device_info)):
            break

    bthprops.BluetoothFindDeviceClose(hFind)
    return devices

print(get_bluetooth_devices())
