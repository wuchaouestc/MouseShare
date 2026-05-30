"""
Config — JSON 配置读写
"""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "MouseShare")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

@dataclass
class Config:
    device_name: str = ""
    instance_id: str = ""
    layout_direction: str = "right"  # up/down/left/right
    corner_dead_zone: int = 8
    trusted_devices: List[dict] = field(default_factory=list)
    last_connected: str = ""
    auto_reconnect: bool = True
    auto_start: bool = False
    log_level: str = "INFO"

def load() -> Config:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(CONFIG_PATH):
        return Config()
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = Config()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg
    except (json.JSONDecodeError, OSError):
        return Config()

def save(cfg: Config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2, ensure_ascii=False)

def get_log_dir() -> str:
    path = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "MouseShare", "logs")
    os.makedirs(path, exist_ok=True)
    return path
