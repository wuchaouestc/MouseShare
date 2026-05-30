"""
Transport — 抽象传输层 + RFCOMM WinSock 实现

优先使用 PyBluez，若不可用则回退到纯 ctypes + WinSock。
"""
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)

SERVICE_UUID = "00001101-0000-1000-8000-00805F9B34FB"
SERVICE_NAME = "MouseShare"
DEFAULT_CHUNK = 4096
RFCOMM_PORT = 1

class TransportError(Exception):
    pass

class Transport(ABC):
    """传输抽象接口"""
    @abstractmethod
    def connect(self, address: str, port: int = 0, timeout: float = 15.0) -> bool:
        ...

    @abstractmethod
    def send(self, data: bytes) -> int:
        ...

    @abstractmethod
    def recv(self, timeout: float = 1.0) -> Optional[bytes]:
        ...

    @abstractmethod
    def close(self):
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...


class WinSockRfcommClient(Transport):
    """ctypes + WinSock 实现的 RFCOMM 客户端"""
    def __init__(self):
        self._sock = None
        self._connected = False
        self._lock = threading.Lock()
        self._ctypes = None
        self._winsock = None

    def _init_winsock(self):
        if self._ctypes is not None:
            return
        import ctypes
        from ctypes import wintypes
        self._ctypes = ctypes
        ws2 = ctypes.WinDLL("ws2_32.dll")

        self.AF_BTH = 32
        self.BTHPROTO_RFCOMM = 3
        self.SOCK_STREAM = 1

        class SOCKADDR_BTH(ctypes.Structure):
            _fields_ = [
                ("addressFamily", wintypes.ULONG),
                ("btAddr", wintypes.ULARGE_INTEGER),
                ("serviceClassId", ctypes.c_byte * 16),
                ("port", wintypes.ULONG),
            ]

        self._SOCKADDR_BTH = SOCKADDR_BTH
        # socket
        ws2.socket.restype = ctypes.c_void_p
        ws2.socket.argtypes = [wintypes.INT, wintypes.INT, wintypes.INT]
        # connect
        ws2.connect.restype = wintypes.INT
        ws2.connect.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.INT]
        # send
        ws2.send.restype = wintypes.INT
        ws2.send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.INT, wintypes.INT]
        # recv
        ws2.recv.restype = wintypes.INT
        ws2.recv.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.INT, wintypes.INT]
        # closesocket
        ws2.closesocket.restype = wintypes.INT
        ws2.closesocket.argtypes = [ctypes.c_void_p]
        # ioctlsocket
        ws2.ioctlsocket.restype = wintypes.INT
        ws2.ioctlsocket.argtypes = [ctypes.c_void_p, wintypes.LONG, ctypes.POINTER(wintypes.ULONG)]

        self._ws2 = ws2

    def connect(self, address: str, port: int = 0, timeout: float = 15.0) -> bool:
        self._init_winsock()
        if port == 0:
            port = RFCOMM_PORT
        try:
            sock = self._ws2.socket(self.AF_BTH, self.SOCK_STREAM, self.BTHPROTO_RFCOMM)
            if sock is None or sock == -1:
                return False

            # Parse MAC address "XX:XX:XX:XX:XX:XX" -> 64-bit
            bt_addr = 0
            parts = address.replace("-", ":").split(":")
            for p in parts:
                bt_addr = (bt_addr << 8) | int(p, 16)

            addr = self._SOCKADDR_BTH()
            addr.addressFamily = self.AF_BTH
            addr.btAddr = bt_addr
            addr.port = port

            addr_size = self._ctypes.sizeof(addr)
            rc = self._ws2.connect(sock, self._ctypes.byref(addr), addr_size)
            if rc != 0:
                self._ws2.closesocket(sock)
                return False

            # Set non-blocking
            mode = self._ctypes.c_ulong(1)
            self._ws2.ioctlsocket(sock, 0x8004667E, self._ctypes.byref(mode))  # FIONBIO

            self._sock = sock
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"RFCOMM connect failed: {e}")
            return False

    def send(self, data: bytes) -> int:
        if not self._sock or not self._connected:
            raise TransportError("Not connected")
        buf = self._ctypes.create_string_buffer(data, len(data))
        try:
            sent = self._ws2.send(self._sock, buf, len(data), 0)
            if sent < 0:
                self._connected = False
                raise TransportError("Send failed")
            return sent
        except Exception as e:
            self._connected = False
            raise TransportError(f"Send error: {e}")

    def recv(self, timeout: float = 1.0) -> Optional[bytes]:
        if not self._sock or not self._connected:
            return None
        buf = self._ctypes.create_string_buffer(DEFAULT_CHUNK)
        try:
            rc = self._ws2.recv(self._sock, buf, DEFAULT_CHUNK, 0)
            if rc > 0:
                return buf.raw[:rc]
            elif rc == 0:
                self._connected = False
                return None
            else:
                # WSAEWOULDBLOCK
                return b""
        except Exception:
            return None

    def close(self):
        self._connected = False
        if self._sock:
            try:
                self._ws2.closesocket(self._sock)
            except Exception:
                pass
            self._sock = None

    @property
    def is_connected(self) -> bool:
        return self._connected


class PyBluezRfcommClient(Transport):
    """PyBluez RFCOMM 客户端"""
    def __init__(self):
        self._sock = None
        self._connected = False

    def connect(self, address: str, port: int = 0, timeout: float = 15.0) -> bool:
        try:
            import bluetooth
            self._sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self._sock.settimeout(timeout)
            self._sock.connect((address, port if port > 0 else 1))
            self._sock.settimeout(1.0)
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"PyBluez connect failed: {e}")
            return False

    def send(self, data: bytes) -> int:
        if not self._sock or not self._connected:
            raise TransportError("Not connected")
        try:
            return self._sock.send(data)
        except Exception as e:
            self._connected = False
            raise TransportError(f"Send error: {e}")

    def recv(self, timeout: float = 1.0) -> Optional[bytes]:
        if not self._sock or not self._connected:
            return None
        try:
            self._sock.settimeout(timeout)
            data = self._sock.recv(DEFAULT_CHUNK)
            return data if data else b""
        except Exception:
            return b""

    def close(self):
        self._connected = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    @property
    def is_connected(self) -> bool:
        return self._connected


def create_rfcomm_client() -> Transport:
    """工厂函数：优先 PyBluez，失败用 WinSock"""
    try:
        import bluetooth  # noqa: F401
        logger.info("Using PyBluez for RFCOMM")
        return PyBluezRfcommClient()
    except ImportError:
        logger.info("PyBluez not found, using ctypes+WinSock fallback")
        return WinSockRfcommClient()
