"""
状态机 — Host/Target 统一状态定义
"""
from enum import Enum, auto
import threading
import time
import logging

logger = logging.getLogger(__name__)

class AgentState(Enum):
    STARTING = auto()
    IDLE = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    HOSTING = auto()
    TARGETING = auto()
    SUSPENDED = auto()
    RECOVERING = auto()
    EXITING = auto()

class AgentRole(Enum):
    HOST = auto()
    TARGET = auto()

VALID_TRANSITIONS = {
    AgentState.STARTING:  {AgentState.IDLE},
    AgentState.IDLE:      {AgentState.CONNECTING, AgentState.SUSPENDED, AgentState.EXITING},
    AgentState.CONNECTING:{AgentState.CONNECTED, AgentState.IDLE, AgentState.RECOVERING},
    AgentState.CONNECTED: {AgentState.HOSTING, AgentState.TARGETING, AgentState.SUSPENDED,
                            AgentState.RECOVERING, AgentState.IDLE, AgentState.EXITING},
    AgentState.HOSTING:   {AgentState.CONNECTED, AgentState.SUSPENDED, AgentState.RECOVERING,
                            AgentState.IDLE, AgentState.EXITING},
    AgentState.TARGETING: {AgentState.CONNECTED, AgentState.SUSPENDED, AgentState.RECOVERING,
                            AgentState.IDLE, AgentState.EXITING},
    AgentState.SUSPENDED: {AgentState.IDLE, AgentState.CONNECTING, AgentState.RECOVERING,
                            AgentState.EXITING},
    AgentState.RECOVERING:{AgentState.CONNECTED, AgentState.IDLE, AgentState.CONNECTING,
                            AgentState.EXITING},
    AgentState.EXITING:   set(),
}

class StateMachine:
    def __init__(self, name: str = "Agent"):
        self.name = name
        self._state = AgentState.STARTING
        self._lock = threading.Lock()
        self._observers = []
        self._state_timestamps = {self._state: time.time()}

    @property
    def state(self) -> AgentState:
        with self._lock:
            return self._state

    def can_transition(self, target: AgentState) -> bool:
        with self._lock:
            return target in VALID_TRANSITIONS.get(self._state, set())

    def transition(self, target: AgentState) -> bool:
        with self._lock:
            if target not in VALID_TRANSITIONS.get(self._state, set()):
                logger.warning(f"[{self.name}] 非法状态转换: {self._state.name} -> {target.name}")
                return False
            old = self._state
            self._state = target
            self._state_timestamps[target] = time.time()
        logger.info(f"[{self.name}] {old.name} -> {target.name}")
        for cb in self._observers:
            try:
                cb(old, target)
            except Exception:
                pass
        return True

    def force_transition(self, target: AgentState):
        """紧急状态切换（绕过合法性检查），用于恢复场景"""
        with self._lock:
            old = self._state
            self._state = target
            self._state_timestamps[target] = time.time()
        logger.warning(f"[{self.name}] 强制转换: {old.name} -> {target.name}")
        for cb in self._observers:
            try:
                cb(old, target)
            except Exception:
                pass

    def time_in_state(self) -> float:
        with self._lock:
            ts = self._state_timestamps.get(self._state, 0)
            return time.time() - ts

    def add_observer(self, callback):
        self._observers.append(callback)

    @property
    def is_controlling(self) -> bool:
        return self.state in (AgentState.HOSTING, AgentState.TARGETING)

    @property
    def is_connected(self) -> bool:
        return self.state in (AgentState.CONNECTED, AgentState.HOSTING, AgentState.TARGETING)
