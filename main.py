"""
MouseShare — 蓝牙鼠标共享工具

入口文件，支持 Host 模式和 Target 模式。
用法:
  python main.py                          # 启动 GUI（自动判断角色）
  python main.py --host <MAC>             # 作为 Host，连接到指定 Target MAC
  python main.py --target                 # 作为 Target，等待 Host 连接
"""
import sys
import os
import argparse
import logging
import signal

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from src.shared.config import Config, load, save
from src.shared.transport import create_rfcomm_client
from src.shared.peer_agent import PeerAgent
from src.host.state_machine import HostAgent
from src.target.state_machine import TargetAgent
from src.ui.main_window import MainWindow
from src.ui.tray import TrayIcon

logger = logging.getLogger(__name__)


def setup_logging():
    """配置日志"""
    from src.shared.config import get_log_dir
    log_dir = get_log_dir()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(log_dir, "mouseshare.log"), encoding="utf-8"),
        ],
    )
    # 减少第三方库日志
    logging.getLogger("PySide6").setLevel(logging.WARNING)
    logging.getLogger("pynput").setLevel(logging.WARNING)


def run_peer(config: Config):
    """以 Peer 模式运行：同时监听和准备主动连接"""
    agent = PeerAgent()
    agent.set_direction(config.layout_direction)

    def on_exit():
        agent.stop()
        QApplication.quit()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow(agent=agent, config=config)
    tray = TrayIcon()
    tray.open_requested.connect(window.show)
    tray.open_requested.connect(window.raise_)
    tray.suspend_toggled.connect(lambda: agent.suspend() if agent.sm.is_controlling else agent.resume())
    tray.reconnect_requested.connect(lambda: None)
    tray.exit_requested.connect(on_exit)

    agent.start()

    def check_role():
        import time
        last_role = "peer"
        while True:
            time.sleep(0.5)
            if agent.role != last_role:
                last_role = agent.role
                if agent.role == "host":
                    tray.show_notification("MouseShare", "已作为主控端连接")
                    tray.set_icon_state("connected")
                elif agent.role == "target":
                    tray.show_notification("MouseShare", "已作为被控端连接")
                    tray.set_icon_state("connected")
                break

    import threading
    threading.Thread(target=check_role, daemon=True).start()

    window.show()
    sys.exit(app.exec())


def run_host(config: Config, address: str):
    """以 Host 模式运行"""
    agent = HostAgent()
    transport = create_rfcomm_client()
    agent.set_transport(transport)
    agent.set_direction(config.layout_direction)
    agent.set_last_connection(address)

    def on_exit():
        agent.stop()
        QApplication.quit()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow(agent=agent, config=config)
    tray = TrayIcon()
    tray.open_requested.connect(window.show)
    tray.open_requested.connect(window.raise_)
    tray.suspend_toggled.connect(lambda: agent.suspend() if agent.sm.is_controlling else agent.resume())
    tray.reconnect_requested.connect(lambda: agent.connect(address))
    tray.exit_requested.connect(on_exit)

    agent.start()
    # 自动连接
    if address:
        import threading
        threading.Thread(target=lambda: _auto_connect(agent, address, tray), daemon=True).start()

    window.show()
    sys.exit(app.exec())


def _auto_connect(agent, address, tray):
    import time
    time.sleep(1)
    ok, err = agent.connect(address)
    if ok:
        tray.show_notification("MouseShare", f"已连接到 {address}")
    else:
        tray.show_notification("MouseShare", f"连接失败: {address}\n{err}")


def run_target(config: Config):
    """以 Target 模式运行"""
    agent = TargetAgent()

    def on_exit():
        agent.stop()
        QApplication.quit()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow(agent=agent, config=config)
    tray = TrayIcon()
    tray.open_requested.connect(window.show)
    tray.open_requested.connect(window.raise_)
    tray.exit_requested.connect(on_exit)

    agent.start()

    # 检测到连接时更新状态
    def check_connection():
        import time
        while True:
            time.sleep(1)
            if agent.server.is_connected and agent.sm.state.value == 2:  # IDLE
                agent.set_connected()
                tray.show_notification("MouseShare", "有设备已连接")
                tray.set_icon_state("connected")
                break

    import threading
    threading.Thread(target=check_connection, daemon=True).start()

    window.show()
    sys.exit(app.exec())


def main():
    parser = argparse.ArgumentParser(description="MouseShare — 蓝牙鼠标共享工具")
    parser.add_argument("--host", type=str, metavar="MAC", help="以 Host 模式运行，连接指定 MAC 地址")
    parser.add_argument("--target", action="store_true", help="以 Target 模式运行，等待连接")
    args = parser.parse_args()

    setup_logging()
    config = load()
    logger.info(f"MouseShare starting, layout={config.layout_direction}")

    if args.target:
        logger.info("Running as Target")
        run_target(config)
    elif args.host:
        logger.info(f"Running as Host, connecting to {args.host}")
        run_host(config, args.host)
    else:
        logger.info("Running in Peer mode")
        run_peer(config)


if __name__ == "__main__":
    main()
