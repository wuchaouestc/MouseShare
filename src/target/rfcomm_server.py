"""
RFCOMM Server — Target 端蓝牙服务监听

接受 Host 的 RFCOMM 连接，提供接收服务。
"""
import socket
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

SERVICE_NAME = "MouseShare"
SERVICE_UUID = "00001101-0000-1000-8000-00805F9B34FB"
DEFAULT_CHUNK = 4096


class RfcommServer:
    """RFCOMM Server（纯 socket 实现）"""
    def __init__(self):
        self._sock = None
        self._client = None
        self._client_addr = None
        self._running = False
        self._connected = False
        self._listen_thread = None
        self._lock = threading.Lock()

    def start(self, port: int = 0) -> bool:
        """启动 RFCOMM 服务，返回是否成功"""
        try:
            # 使用标准 Winsock RFCOMM
            self._sock = socket.socket(socket.AF_BTH, socket.SOCK_STREAM, socket.BTHPROTO_RFCOMM)
            self._sock.bind(("", port))
            self._sock.listen(1)
            self._sock.settimeout(2.0)
            self._running = True
            self._listen_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self._listen_thread.start()
            logger.info(f"RFCOMM Server listening on port {port}")
            return True
        except Exception as e:
            logger.error(f"Failed to start RFCOMM Server: {e}")
            return False

    def start_pybluez(self, port: int = 0) -> bool:
        """使用 PyBluez 启动 RFCOMM 服务"""
        try:
            import bluetooth
            self._pbsock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self._pbsock.bind(("", port if port > 0 else bluetooth.PORT_ANY))
            self._pbsock.listen(1)
            self._pbsock.settimeout(2.0)

            bluetooth.advertise_service(
                self._pbsock, SERVICE_NAME,
                service_id=SERVICE_UUID,
                service_classes=[SERVICE_UUID, bluetooth.SERIAL_PORT_CLASS],
                profiles=[bluetooth.SERIAL_PORT_PROFILE],
            )
            self._running = True
            self._listen_thread = threading.Thread(target=self._accept_loop_pybluez, daemon=True)
            self._listen_thread.start()
            logger.info("RFCOMM Server (PyBluez) started with SDP advertisement")
            return True
        except Exception as e:
            logger.error(f"PyBluez server start failed: {e}")
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
                logger.info(f"Client connected: {addr}")
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.error(f"Accept error: {e}")
                break

    def _accept_loop_pybluez(self):
        while self._running:
            try:
                client, addr = self._pbsock.accept()
                client.settimeout(1.0)
                with self._lock:
                    if hasattr(self, '_pbclient') and self._pbclient:
                        try:
                            self._pbclient.close()
                        except Exception:
                            pass
                    self._pbclient = client
                    self._client_addr = addr
                    self._connected = True
                logger.info(f"Client connected (PyBluez): {addr}")
            except Exception as e:
                if self._running:
                    logger.error(f"PyBluez accept error: {e}")
                break

    def recv(self, timeout: float = 1.0) -> Optional[bytes]:
        with self._lock:
            if not self._connected:
                return None
            try:
                sock = self._pbclient if hasattr(self, '_pbclient') and self._pbclient else self._client
            except AttributeError:
                return None

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
        except Exception:
            self._connected = False
            return None

    def send(self, data: bytes) -> int:
        sock = None
        with self._lock:
            try:
                sock = self._pbclient if hasattr(self, '_pbclient') and self._pbclient else self._client
            except AttributeError:
                pass
        if not sock:
            return -1
        try:
            return sock.send(data)
        except Exception:
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
            if hasattr(self, '_pbclient') and self._pbclient:
                try:
                    self._pbclient.close()
                except Exception:
                    pass
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if hasattr(self, '_pbsock') and self._pbsock:
            try:
                self._pbsock.close()
            except Exception:
                pass
        logger.info("RFCOMM Server stopped")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def client_address(self):
        return self._client_addr
