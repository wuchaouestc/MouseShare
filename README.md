# MouseShare — 蓝牙鼠标共享工具

通过蓝牙实现两台 Windows PC 之间的鼠标光标共享。

## 快速开始

### 环境要求

- Windows 10 22H2 或 Windows 11 23H2/24H2
- Python 3.11+
- 两台 PC 均需支持经典蓝牙 (RFCOMM)
- 推荐蓝牙适配器：Intel AX210/AX211

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行

```bash
# GUI 模式
python main.py

# Host 模式（控制端，连接指定 Target MAC）
python main.py --host XX:XX:XX:XX:XX:XX

# Target 模式（被控端，等待连接）
python main.py --target
```

### 运行测试

```bash
python -m pytest tests/ -v
```

### 构建 exe

双击运行 `scripts/build.bat`，或执行：

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name MouseShare main.py
```

输出文件位于 `dist/MouseShare.exe`。

## 使用方式

1. 在两台 PC 上安装 MouseShare
2. 系统设置中完成蓝牙配对
3. Target 端以 `--target` 启动
4. Host 端以 `--host <MAC>` 启动
5. 在 Host 端设置 Target 所在方向
6. 鼠标移动到屏幕边缘即可控制 Target

**紧急解锁**：按 Ctrl+Alt+Shift+M 可在任意状态下恢复 Host 本地鼠标控制。

## 项目结构

```
MouseShare/
├── main.py                    # 入口
├── requirements.txt
├── src/
│   ├── shared/                # 共享模块
│   │   ├── protocol.py        # 帧协议编解码
│   │   ├── transport.py       # RFCOMM 传输层
│   │   ├── config.py          # JSON 配置
│   │   └── state_machine.py   # 状态机
│   ├── host/                  # Host（主控端）
│   │   ├── input_capture.py   # 鼠标 Hook
│   │   ├── boundary_engine.py # 边界检测
│   │   ├── cursor_controller.py # 光标锁定
│   │   └── state_machine.py   # Host Agent
│   ├── target/                # Target（被控端）
│   │   ├── rfcomm_server.py   # RFCOMM Server
│   │   ├── input_injector.py  # SendInput 注入
│   │   └── state_machine.py   # Target Agent
│   └── ui/                    # PySide6 GUI
│       ├── main_window.py
│       ├── device_list.py
│       ├── layout_config.py
│       ├── status_page.py
│       └── tray.py
├── tests/                     # 单元测试
├── scripts/build.bat          # 构建脚本
└── docs/                      # 文档
```

## 技术栈

- Python 3.11 — 快速验证原型
- PySide6 — GUI 框架
- pynput — 全局鼠标 Hook
- ctypes — Win32 API (SendInput, ClipCursor, Bluetooth)
- PyBluez / WinSock — 蓝牙 RFCOMM 通信

## 许可证

MIT
