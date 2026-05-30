"""
PeerAgent — 同时运行监听端和主动连接端，连接方向决定角色。
"""
import logging
import threading
import time

from src.host.state_machine import HostAgent
from src.shared.state_machine import AgentState
from src.shared.transport import create_rfcomm_client
from src.target.state_machine import TargetAgent

logger = logging.getLogger(__name__)


class PeerAgent:
    def __init__(self):
        self.host = HostAgent()
        self.target = TargetAgent()
        self.host.set_transport(create_rfcomm_client())
        self.sm = self.host.sm
        self.server = self.target.server
        self.role = "peer"
        self._running = False
        self._lock = threading.Lock()
        self._monitor_thread = None

    def set_direction(self, direction: str):
        self.host.set_direction(direction)

    def set_last_connection(self, address: str, port: int = 0):
        self.host.set_last_connection(address, port)

    def start(self):
        self._running = True
        self.host.start()
        self.target.start()
        self._monitor_thread = threading.Thread(target=self._monitor_inbound, daemon=True)
        self._monitor_thread.start()
        logger.info("PeerAgent started")

    def stop(self):
        self._running = False
        self.host.stop()
        self.target.stop()
        logger.info("PeerAgent stopped")

    def connect(self, address: str, port: int = 0) -> tuple:
        with self._lock:
            if self.role == "target" and self.target.sm.is_connected:
                return False, "本机已作为被控端连接，不能同时主动连接"
            ok, err = self.host.connect(address, port)
            if ok:
                self.role = "host"
                self.sm = self.host.sm
                self.target.stop()
                logger.info("PeerAgent role selected: host")
            return ok, err

    def suspend(self):
        if self.role == "host":
            self.host.suspend()
        elif self.role == "target":
            self.target.sm.transition(AgentState.SUSPENDED)

    def resume(self):
        if self.role == "host":
            self.host.resume()
        elif self.role == "target" and self.target.sm.state == AgentState.SUSPENDED:
            self.target.sm.transition(AgentState.CONNECTED)

    def _monitor_inbound(self):
        while self._running:
            time.sleep(0.2)
            if self.role == "host":
                continue
            if self.target.server.is_connected:
                with self._lock:
                    if self.role == "host":
                        continue
                    self.role = "target"
                    self.target.set_connected()
                    self.host.stop()
                    self.sm = self.target.sm
                    logger.info("PeerAgent role selected: target")
                break
