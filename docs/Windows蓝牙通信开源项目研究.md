# Windows 蓝牙通信 — 开源项目研究

> 研究日期：2026-05-30  
> 目的：为 MouseShare 蓝牙鼠标共享工具寻找 Windows 蓝牙通信的学习参考和代码范本

---

## 一、Python — 直接对口 MouseShare

| 项目 | Stars | 说明 |
|------|-------|------|
| [hbldh/bleak](https://github.com/hbldh/bleak) | ⭐2,418 | **推荐首选！** 跨平台 BLE 客户端，`asyncio` 驱动，Windows/Linux/macOS 通吃，API 设计现代化，文档完善，是 Python BLE 领域的事实标准 |
| [pybluez/pybluez](https://github.com/pybluez/pybluez) | ⭐2,398 | **经典蓝牙（RFCOMM）** Python 扩展模块，蓝牙 Socket 编程的鼻祖级库。MouseShare 的 RFCOMM 方案与它属于同一技术路线，Windows 上兼容性有限但架构思想值得学习 |
| [Jakeler/ble-serial](https://github.com/Jakeler/ble-serial) | ⭐377 | "BLE 上的 RFCOMM" — 串口 UART 桥接，Python 实现，适合理解 BLE 串口通信链路 |

### bleak 关键特性
- 扫描/发现 BLE 设备
- 连接/断开设备
- 读写 GATT Characteristic
- 订阅 Notification
- 支持 WinRT（Windows 原生 BLE API）、CoreBluetooth（macOS）、BlueZ（Linux）

### pybluez 关键特性
- RFCOMM Socket 编程（`BluetoothSocket`）
- SDP 服务发现（`find_service`）
- 设备发现（`discover_devices`）
- L2CAP 支持
- Windows 需要安装特定的蓝牙驱动栈（如 Microsoft Bluetooth Stack）

---

## 二、C++ — Windows 原生蓝牙编程

| 项目 | Stars | 说明 |
|------|-------|------|
| [cmwahl/WahlSoBlue](https://github.com/cmwahl/WahlSoBlue) | ⭐1 | 🎯 **高度相关！** 轻量级 C++ RFCOMM 蓝牙库，直接调用 Windows Winsock API 进行蓝牙通信，代码精简，非常适合学习 Windows 原生蓝牙 Socket 编程。技术栈与 MouseShare 底层直接相关 |
| [finallyfunctional/bluetooth-windows-esp32-example](https://github.com/finallyfunctional/bluetooth-windows-esp32-example) | ⭐20 | Windows 10 蓝牙 Socket ↔ ESP32 通信的完整示例，C++ 实现。展示了从设备发现到 Socket 连接建立的全流程 |
| [rohitsangwan01/win_ble](https://github.com/rohitsangwan01/win_ble) | ⭐37 | Flutter Windows Desktop 的 BLE 插件，底层是 C++ 调用 Windows BLE API（WinRT），可作为学习 Windows Runtime 蓝牙接口的参考资料 |
| [blackhack/Packet](https://github.com/blackhack/Packet) | ⭐2 | 通用数据包管理框架，支持串口、WebSocket 和蓝牙 RFCOMM 三种传输层，C++ 实现。适合学习蓝牙通信的数据包封装/解析模式 |

### WahlSoBlue 技术要点
- 基于 Windows Winsock2 的蓝牙 Socket（AF_BTH）
- RFCOMM 服务发现与连接建立
- 轻量设计，核心代码量小，适合研读
- 展示了 `WSAStartup` → `socket(AF_BTH)` → `SOCKADDR_BTH` → `connect` 的完整链路

### Windows 蓝牙 Socket 编程关键 API
```
WSAStartup()           → 初始化 Winsock
socket(AF_BTH, ...)    → 创建蓝牙 Socket
WSAQUERYSET            → 蓝牙设备查询结构
WSALookupServiceBegin  → 开始设备发现
SOCKADDR_BTH           → 蓝牙地址结构（含 MAC + GUID）
connect() / send()     → 连接与数据发送
```

---

## 三、C# — Windows 蓝牙最成熟生态

| 项目 | Stars | 说明 |
|------|-------|------|
| [inthehand/32feet](https://github.com/inthehand/32feet) | ⭐982 | 🏆 **C# 领域事实标准！** .NET 全功能蓝牙库，支持经典蓝牙、BLE、RFCOMM、OBEX（文件传输），是 Windows 蓝牙编程最成熟的开源方案。即便不直接用 C#，其 API 设计和抽象层次也值得学习 |
| [timschneeb/GalaxyBudsClient](https://github.com/timschneeb/GalaxyBudsClient) | ⭐5,007 | Galaxy Buds 桌面客户端，C# + BLE，**真实商业级案例**。展示了如何在生产场景中管理蓝牙连接生命周期、处理断连重连、UI 与蓝牙状态的同步等 |
| [miyu/CampfireNet](https://github.com/miyu/CampfireNet) | ⭐23 | C# 蓝牙 Mesh 组网（Windows/Android），理解多设备蓝牙拓扑和 P2P 通信模式的绝佳参考 |
| [tanaka-takayoshi/BluetoothRfcommUniversalApp](https://github.com/tanaka-takayoshi/BluetoothRfcommUniversalApp) | ⭐2 | UWP 蓝牙 RFCOMM 示例，直接展示 `Windows.Devices.Bluetooth.Rfcomm` API 用法 |
| [savignas/Win10NotificationsBluetooth](https://github.com/savignas/Win10NotificationsBluetooth) | ⭐3 | Windows 10 ↔ Android 通过蓝牙 RFCOMM 同步通知，展示了跨平台蓝牙 RFCOMM 通信的完整实现 |
| [oliveredget/BluetoothRfcommChat](https://github.com/oliveredget/BluetoothRfcommChat) | ⭐0 | C# RFCOMM 聊天示例，最简单的 RFCOMM 入门级代码 |

### 32feet 技术要点
- `BluetoothClient` — 经典蓝牙设备发现与连接
- `BluetoothListener` — 服务端 RFCOMM 监听
- `BluetoothDeviceInfo` — 设备信息封装
- 支持 32feet.NET NuGet 包，开箱即用

---

## 四、JavaScript / Node.js

| 项目 | Stars | 说明 |
|------|-------|------|
| [eelcocramer/node-bluetooth-serial-port](https://github.com/eelcocramer/node-bluetooth-serial-port) | ⭐508 | Node.js 蓝牙串口通信库，Windows 兼容，C++ 原生插件（N-API）实现。`BluetoothSerialPort` 类封装了完整的 RFCOMM Socket 操作 |

---

## 五、微软官方示例（必看！）

| 项目 | Stars | 说明 |
|------|-------|------|
| [microsoft/Windows-universal-samples](https://github.com/microsoft/Windows-universal-samples) | ⭐9,691 | 包含 `BluetoothRfcommChat` 等官方蓝牙示例（C#/C++），直接展示微软推荐的最佳实践。搜索 `Bluetooth` 关键词可找到十多个蓝牙相关示例 |
| [microsoft/Windows-classic-samples](https://github.com/microsoft/Windows-classic-samples) | ⭐5,613 | 经典桌面 API 示例合集，包含基于 Winsock 的蓝牙编程示例 |
| [microsoft/Windows-driver-samples](https://github.com/microsoft/Windows-driver-samples) | ⭐7,745 | 蓝牙驱动层示例，深入了解 Windows 蓝牙协议栈的底层架构。适合进阶学习 Windows 蓝牙驱动模型（BTHUSB、RFCOMM 驱动等） |

### Windows-universal-samples 中蓝牙示例清单
- `BluetoothRfcommChat` — C# RFCOMM 聊天
- `BluetoothRfcommChat (C++)` — C++ RFCOMM 聊天
- `BluetoothLE` — 低功耗蓝牙发现与通信
- `BluetoothAdvertisement` — 蓝牙广播
- `DeviceEnumerationAndPairing` — 蓝牙设备枚举与配对

---

## 六、同类 KVM 共享工具 — 架构参考

| 项目 | Stars | 说明 |
|------|-------|------|
| [debauchee/barrier](https://github.com/debauchee/barrier) | ⭐30,595 | 开源 KVM 软件，支持 Windows/macOS/Linux 跨设备键鼠共享。虽然底层是 TCP/IP 而非蓝牙，但其**架构设计**（客户端-服务端模型、输入事件序列化、边界检测、光标控制）与 MouseShare 高度重合 |
| [input-leap/input-leap](https://github.com/input-leap/input-leap) | ⭐8,008 | Barrier 的活跃 fork，代码更现代，支持 libei 输入模拟协议，是学习跨设备输入共享的绝佳参考 |

### Barrier 架构要点（可借鉴的设计模式）
```
┌─────────────┐     TCP/IP      ┌─────────────┐
│   Server    │ ←─────────────→ │   Client    │
│ (键盘鼠标所在) │  输入事件/剪贴板  │ (被控端)     │
└─────────────┘                 └─────────────┘

核心模块:
  - Input Capture  — 捕获本地键盘鼠标事件
  - Event Serialization — 事件序列化/反序列化
  - Screen Boundary Detection — 屏幕边界检测（光标移出触发切换）
  - Input Injection — 在远程 PC 注入输入事件
  - Clipboard Sync — 剪贴板同步
```

---

## 🎯 针对 MouseShare 的学习路径建议

### 第一阶段：理解 Windows 蓝牙通信基础
1. **蓝牙 API 底层** → `cmwahl/WahlSoBlue` — 理解 C++ Winsock RFCOMM 编程（代码量小，最容易吃透）
2. **Python RFCOMM 全链路** → `pybluez/pybluez` 官方示例 — 理解 Python 侧蓝牙 Socket 编程
3. **微软 WinRT 蓝牙** → `microsoft/Windows-universal-samples` 中的 `BluetoothRfcommChat`

### 第二阶段：研究蓝牙通信架构设计
4. **BLE 通信模型** → `hbldh/bleak` — 理解现代 async BLE 编程范式
5. **多设备拓扑** → `miyu/CampfireNet` — 理解蓝牙 P2P 组网
6. **C# 成熟方案** → `inthehand/32feet` — 学习蓝牙库的 API 设计哲学

### 第三阶段：参考同类跨设备输入共享架构
7. **KVM 架构设计** → `debauchee/barrier` — 研究输入捕获、事件序列化、边界检测、输入注入
8. **生产级蓝牙客户端** → `timschneeb/GalaxyBudsClient` — 学习连接生命周期管理和状态同步

---

## 📊 技术栈对比

| 技术栈 | 蓝牙支持 | 开发难度 | 生态成熟度 | 适合场景 |
|--------|---------|---------|-----------|---------|
| Python + pybluez | RFCOMM 经典蓝牙 | ⭐⭐ | ⭐⭐⭐ | 快速原型、跨平台 |
| Python + bleak | BLE 低功耗 | ⭐⭐ | ⭐⭐⭐⭐ | BLE 设备通信 |
| C++ + Winsock | RFCOMM/BLE | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 高性能、系统级 |
| C# + 32feet | RFCOMM/BLE/OBEX | ⭐⭐ | ⭐⭐⭐⭐⭐ | Windows 桌面应用 |
| C# + WinRT | RFCOMM/BLE | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | UWP/Windows App SDK |

---

## 🔗 延伸资源

- [Microsoft Windows.Devices.Bluetooth 文档](https://docs.microsoft.com/en-us/uwp/api/windows.devices.bluetooth)
- [Bluetooth Classic (RFCOMM) on Windows](https://learn.microsoft.com/en-us/windows/uwp/devices-sensors/send-or-receive-files-with-rfcomm)
- [Winsock Bluetooth Programming](https://learn.microsoft.com/en-us/windows/win32/bluetooth/bluetooth-programming-with-windows-sockets)
- [32feet.NET 文档](https://inthehand.com/library/32feet/)
- [bleak 文档](https://bleak.readthedocs.io/)

---

> 研究人：ArkClaw 伙伴_822  
> 关联项目：[MouseShare](https://github.com/wuchaouestc/MouseShare) — 蓝牙鼠标共享工具
