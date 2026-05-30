"""
RFCOMM Server — Target 端蓝牙服务监听

接受 Host 的 RFCOMM 连接，提供接收服务。
"""
import ctypes
import logging
import socket
import threading
import time
from ctypes import wintypes
from typing import Optional

logger = logging.getLogger(__name__)

SERVICE_NAME = "MouseShare"
SERVICE_UUID = "00001101-0000-1000-8000-00805F9B34FB"
DEFAULT_CHUNK = 4096
RFCOMM_PORT = 1
RFCOMM_PORTS = tuple(range(1, 31))
BT_PORT_ANY = 0xFFFFFFFF
WSAEWOULDBLOCK = 10035
FIONBIO = 0x8004667E


class BLUETOOTH_FIND_RADIO_PARAMS(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD)]


class BLUETOOTH_RADIO_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("address", ctypes.c_ulonglong),
        ("szName", wintypes.WCHAR * 248),
        ("ulClassofDevice", wintypes.ULONG),
        ("lmpSubversion", wintypes.USHORT),
        ("manufacturer", wintypes.USHORT),
    ]


def _format_bth_addr(addr: int) -> str:
    return ":".join(f"{(addr >> (8 * i)) & 0xFF:02X}" for i in range(5, -1, -1))


def _wsa_error_str(code: int) -> str:
    try:
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.kernel32.FormatMessageW(
            0x1000 | 0x200, None, code, 0, buf, 512, None
        )
        desc = buf.value.strip()
        if desc:
            return f"{desc} (WSA {code})"
    except Exception:
        pass
    return f"WSA 错误 {code}"


class RfcommServer:
    """RFCOMM Server"""
    def __init__(self):
        self._sock = None
        self._client = None
        self._client_addr = None
        self._running = False
        self._connected = False
        self._listen_thread = None
        self._lock = threading.Lock()
        self._ctypes = None
        self._ws2 = None
        self._SOCKADDR_BTH = None
        self._ctypes_server = None
        self._ctypes_client = None
        self._last_error = ""
        self.bound_port = 0

    def start(self, port: int = RFCOMM_PORT) -> bool:
        """启动 RFCOMM 服务，返回是否成功"""
        if hasattr(socket, "AF_BTH") and hasattr(socket, "BTHPROTO_RFCOMM"):
            try:
                self._sock = socket.socket(socket.AF_BTH, socket.SOCK_STREAM, socket.BTHPROTO_RFCOMM)
                self._sock.bind(("", port))
                self._sock.listen(1)
                self._sock.settimeout(2.0)
                self._running = True
                self.bound_port = port
                self._listen_thread = threading.Thread(target=self._accept_loop, daemon=True)
                self._listen_thread.start()
                logger.info("RFCOMM Server listening on port %s", port)
                return True
            except Exception as e:
                self._last_error = str(e)
                logger.warning("Python socket RFCOMM start failed: %s", e)
                self._close_python_server()
        else:
            logger.info("Python socket does not expose AF_BTH, using ctypes WinSock fallback")

        return self._start_ctypes(port)

    def _candidate_ports(self, port: int):
        if port > 0:
            return (BT_PORT_ANY, port) + tuple(p for p in RFCOMM_PORTS if p != port)
        return (BT_PORT_ANY,) + RFCOMM_PORTS

    def _local_radio_addresses(self):
        addresses = []
        try:
            bthprops = ctypes.WinDLL("bthprops.cpl")
            bthprops.BluetoothFindFirstRadio.argtypes = [
                ctypes.POINTER(BLUETOOTH_FIND_RADIO_PARAMS), ctypes.POINTER(wintypes.HANDLE)
            ]
            bthprops.BluetoothFindFirstRadio.restype = wintypes.HANDLE
            bthprops.BluetoothFindNextRadio.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE)]
            bthprops.BluetoothFindNextRadio.restype = wintypes.BOOL
            bthprops.BluetoothFindRadioClose.argtypes = [wintypes.HANDLE]
            bthprops.BluetoothFindRadioClose.restype = wintypes.BOOL
            bthprops.BluetoothGetRadioInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(BLUETOOTH_RADIO_INFO)]
            bthprops.BluetoothGetRadioInfo.restype = wintypes.DWORD

            params = BLUETOOTH_FIND_RADIO_PARAMS()
            params.dwSize = ctypes.sizeof(params)
            h_radio = wintypes.HANDLE()
            h_find = bthprops.BluetoothFindFirstRadio(ctypes.byref(params), ctypes.byref(h_radio))
            if not h_find:
                return addresses
            try:
                while True:
                    info = BLUETOOTH_RADIO_INFO()
                    info.dwSize = ctypes.sizeof(info)
                    if bthprops.BluetoothGetRadioInfo(h_radio, ctypes.byref(info)) == 0:
                        addresses.append(int(info.address))
                    ctypes.windll.kernel32.CloseHandle(h_radio)
                    h_radio = wintypes.HANDLE()
                    if not bthprops.BluetoothFindNextRadio(h_find, ctypes.byref(h_radio)):
                        break
            finally:
                bthprops.BluetoothFindRadioClose(h_find)
        except Exception as e:
            logger.warning("枚举本机蓝牙适配器失败: %s", e)
        return addresses

    def _candidate_local_addresses(self):
        radios = self._local_radio_addresses()
        if radios:
            logger.info("发现本机蓝牙适配器: %s", ", ".join(_format_bth_addr(a) for a in radios))
        else:
            logger.warning("未发现本机蓝牙适配器，RFCOMM 服务端可能无法启动")
        return (0,) + tuple(a for a in radios if a)

    def _init_winsock(self) -> bool:
        if self._ws2 is not None:
            return True
        try:
            ws2 = ctypes.WinDLL("ws2_32.dll")
            ws2.WSAStartup.restype = wintypes.INT
            ws2.WSAStartup.argtypes = [wintypes.WORD, ctypes.c_void_p]
            wsa_data = ctypes.create_string_buffer(400)
            rc = ws2.WSAStartup(0x0202, ctypes.byref(wsa_data))
            if rc != 0:
                self._last_error = _wsa_error_str(rc)
                return False

            class SOCKADDR_BTH(ctypes.Structure):
                _fields_ = [
                    ("addressFamily", ctypes.c_ushort),
                    ("btAddr", ctypes.c_ulonglong),
                    ("serviceClassId", ctypes.c_byte * 16),
                    ("port", wintypes.ULONG),
                ]

            self.AF_BTH = 32
            self.BTHPROTO_RFCOMM = 3
            self.SOCK_STREAM = 1
            self.INVALID_SOCKET = ctypes.c_void_p(-1).value
            self._SOCKADDR_BTH = SOCKADDR_BTH

            ws2.socket.restype = ctypes.c_void_p
            ws2.socket.argtypes = [wintypes.INT, wintypes.INT, wintypes.INT]
            ws2.bind.restype = wintypes.INT
            ws2.bind.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.INT]
            ws2.listen.restype = wintypes.INT
            ws2.listen.argtypes = [ctypes.c_void_p, wintypes.INT]
            ws2.accept.restype = ctypes.c_void_p
            ws2.accept.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.INT)]
            ws2.recv.restype = wintypes.INT
            ws2.recv.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.INT, wintypes.INT]
            ws2.send.restype = wintypes.INT
            ws2.send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.INT, wintypes.INT]
            ws2.closesocket.restype = wintypes.INT
            ws2.closesocket.argtypes = [ctypes.c_void_p]
            ws2.ioctlsocket.restype = wintypes.INT
            ws2.ioctlsocket.argtypes = [ctypes.c_void_p, wintypes.LONG, ctypes.POINTER(wintypes.ULONG)]
            ws2.getsockname.restype = wintypes.INT
            ws2.getsockname.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.INT)]
            ws2.WSAGetLastError.restype = wintypes.INT

            self._ctypes = ctypes
            self._ws2 = ws2
            return True
        except Exception as e:
            self._last_error = str(e)
            logger.error("WinSock init failed: %s", e)
            return False

    def _is_invalid_socket(self, sock) -> bool:
        return sock is None or sock == self.INVALID_SOCKET or sock == -1

    def _set_nonblocking(self, sock):
        mode = wintypes.ULONG(1)
        self._ws2.ioctlsocket(sock, FIONBIO, ctypes.byref(mode))

    def _start_ctypes(self, port: int) -> bool:
        if not self._init_winsock():
            logger.error("Failed to initialize WinSock: %s", self._last_error)
            return False

        local_addresses = self._candidate_local_addresses()
        last_error = ""
        for local_addr in local_addresses:
            for candidate_port in self._candidate_ports(port):
                sock = self._ws2.socket(self.AF_BTH, self.SOCK_STREAM, self.BTHPROTO_RFCOMM)
                if self._is_invalid_socket(sock):
                    err = self._ws2.WSAGetLastError()
                    self._last_error = _wsa_error_str(err)
                    logger.error("Failed to create Bluetooth socket: %s", self._last_error)
                    return False

                addr = self._SOCKADDR_BTH()
                addr.addressFamily = self.AF_BTH
                addr.btAddr = local_addr
                addr.port = candidate_port

                rc = self._ws2.bind(sock, ctypes.byref(addr), ctypes.sizeof(addr))
                if rc != 0:
                    err = self._ws2.WSAGetLastError()
                    self._ws2.closesocket(sock)
                    last_error = _wsa_error_str(err)
                    port_label = "BT_PORT_ANY" if candidate_port == BT_PORT_ANY else str(candidate_port)
                    logger.warning(
                        "ctypes RFCOMM bind failed on local=%s port=%s: %s",
                        _format_bth_addr(local_addr) if local_addr else "0",
                        port_label,
                        last_error,
                    )
                    continue

                bound_addr = self._SOCKADDR_BTH()
                bound_len = wintypes.INT(ctypes.sizeof(bound_addr))
                if self._ws2.getsockname(sock, ctypes.byref(bound_addr), ctypes.byref(bound_len)) == 0:
                    actual_port = int(bound_addr.port)
                else:
                    actual_port = candidate_port

                rc = self._ws2.listen(sock, 1)
                if rc != 0:
                    err = self._ws2.WSAGetLastError()
                    self._ws2.closesocket(sock)
                    last_error = _wsa_error_str(err)
                    logger.warning("ctypes RFCOMM listen failed on port %s: %s", actual_port, last_error)
                    continue

                self._set_nonblocking(sock)
                self._ctypes_server = sock
                self._running = True
                self.bound_port = actual_port
                self._listen_thread = threading.Thread(target=self._accept_loop_ctypes, daemon=True)
                self._listen_thread.start()
                logger.info(
                    "RFCOMM Server (ctypes WinSock) listening on local=%s port=%s",
                    _format_bth_addr(local_addr) if local_addr else "0",
                    actual_port,
                )
                return True

        self._last_error = last_error or "没有可用的本机蓝牙适配器或 RFCOMM channel"
        logger.error("ctypes RFCOMM bind failed on all local addresses/channels: %s", self._last_error)
        return False

    def _accept_loop(self):
        while self._running:
            try:
                client, addr = self._sock.accept()
                client.settimeout(1.0)
                with self._lock:
                    if self._client:
                        try:
                            self._client.close()
                        except Exception:
                            pass
                    self._client = client
                    self._client_addr = addr
                    self._connected = True
                logger.info("Client connected: %s", addr)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error("Accept error: %s", e)
                break

    def _accept_loop_ctypes(self):
        while self._running:
            addr = self._SOCKADDR_BTH()
            addr_len = wintypes.INT(ctypes.sizeof(addr))
            client = self._ws2.accept(self._ctypes_server, ctypes.byref(addr), ctypes.byref(addr_len))
            if self._is_invalid_socket(client):
                err = self._ws2.WSAGetLastError()
                if err == WSAEWOULDBLOCK:
                    time.sleep(0.05)
                    continue
                if self._running:
                    logger.error("ctypes RFCOMM accept failed: %s", _wsa_error_str(err))
                time.sleep(0.2)
                continue

            self._set_nonblocking(client)
            with self._lock:
                if self._ctypes_client is not None:
                    self._ws2.closesocket(self._ctypes_client)
                self._ctypes_client = client
                self._client_addr = _format_bth_addr(int(addr.btAddr))
                self._connected = True
            logger.info("Client connected (ctypes WinSock): %s", self._client_addr)

    def recv(self, timeout: float = 1.0) -> Optional[bytes]:
        with self._lock:
            if not self._connected:
                return None
            ctypes_client = self._ctypes_client
            sock = self._client

        if ctypes_client is not None:
            return self._recv_ctypes(ctypes_client, timeout)

        if not sock:
            return None
        try:
            sock.settimeout(timeout)
            data = sock.recv(DEFAULT_CHUNK)
            if not data:
                self._connected = False
                return None
            return data
        except (socket.timeout, BlockingIOError):
            return b""
        except Exception as e:
            logger.error("RFCOMM recv failed: %s", e)
            self._connected = False
            return None

    def _recv_ctypes(self, sock, timeout: float) -> Optional[bytes]:
        deadline = time.time() + timeout
        while self._running:
            buf = ctypes.create_string_buffer(DEFAULT_CHUNK)
            rc = self._ws2.recv(sock, buf, DEFAULT_CHUNK, 0)
            if rc > 0:
                return buf.raw[:rc]
            if rc == 0:
                self._connected = False
                return None
            err = self._ws2.WSAGetLastError()
            if err == WSAEWOULDBLOCK:
                if time.time() >= deadline:
                    return b""
                time.sleep(0.02)
                continue
            logger.error("ctypes RFCOMM recv failed: %s", _wsa_error_str(err))
            self._connected = False
            return None
        return None

    def send(self, data: bytes) -> int:
        with self._lock:
            ctypes_client = self._ctypes_client
            sock = self._client

        if ctypes_client is not None:
            buf = ctypes.create_string_buffer(data, len(data))
            rc = self._ws2.send(ctypes_client, buf, len(data), 0)
            if rc < 0:
                err = self._ws2.WSAGetLastError()
                logger.error("ctypes RFCOMM send failed: %s", _wsa_error_str(err))
                self._connected = False
                return -1
            return rc

        if not sock:
            return -1
        try:
            return sock.send(data)
        except Exception as e:
            logger.error("RFCOMM send failed: %s", e)
            self._connected = False
            return -1

    def stop(self):
        self._running = False
        self._connected = False
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
            if self._ctypes_client is not None:
                try:
                    self._ws2.closesocket(self._ctypes_client)
                except Exception:
                    pass
                self._ctypes_client = None
        self._close_python_server()
        if self._ctypes_server is not None:
            try:
                self._ws2.closesocket(self._ctypes_server)
            except Exception:
                pass
            self._ctypes_server = None
        logger.info("RFCOMM Server stopped")
        self.bound_port = 0

    def _close_python_server(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def client_address(self):
        return self._client_addr
