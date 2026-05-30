"""
MouseShare Protocol — 应用层帧协议编解码

Frame layout (little-endian):
  Magic(2B) | Version(1B) | Type(1B) | Flags(1B) | HdrLen(1B) |
  Sequence(4B) | PayloadLen(2B) | HdrCRC(2B) | Payload(N) | PayloadCRC(4B)

  HdrFields = 12 bytes (before CRC)
  HdrCRC    = 2 bytes
  TotalHdr  = 14 bytes
"""
import struct
import zlib
from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, Tuple

MAGIC = 0x4D53  # "MS"
VERSION = 1
HDR_FIELDS = 12   # Magic(2)+Ver(1)+Type(1)+Flags(1)+HdrLen(1)+Seq(4)+PayloadLen(2)
HDR_CRC = 2
HDR_TOTAL = HDR_FIELDS + HDR_CRC  # 14


class MsgType(IntEnum):
    HELLO = 0x01
    HELLO_ACK = 0x02
    HEARTBEAT = 0x03
    HEARTBEAT_ACK = 0x04
    CONTROL_ENTER = 0x10
    CONTROL_LEAVE = 0x11
    MOUSE_MOVE = 0x20
    MOUSE_BUTTON = 0x21
    MOUSE_WHEEL = 0x22
    ERROR = 0x30
    METRICS = 0x40


class Button(IntEnum):
    LEFT = 1
    RIGHT = 2
    MIDDLE = 3


class ButtonAction(IntEnum):
    PRESS = 1
    RELEASE = 2


@dataclass
class Frame:
    type: int
    sequence: int = 0
    flags: int = 0
    payload: bytes = b""


def _crc16(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFF


def _crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def encode(frame: Frame) -> bytes:
    """Encode Frame -> bytes"""
    hdr = struct.pack("<HBBBB I H",
        MAGIC, VERSION, frame.type, frame.flags, HDR_TOTAL,
        frame.sequence, len(frame.payload))
    hcrc = _crc16(hdr)
    pcrc = _crc32(frame.payload) if frame.payload else 0
    return hdr + struct.pack("<H", hcrc) + frame.payload + struct.pack("<I", pcrc)


def decode(data: bytes) -> Optional[Frame]:
    """Decode bytes -> Frame, or None if incomplete/corrupt"""
    if len(data) < HDR_TOTAL + 4:
        return None

    magic, ver, msg_type, flags, hdr_len, seq, plen = \
        struct.unpack_from("<HBBBB I H", data, 0)

    if magic != MAGIC:
        return None

    # Verify header CRC (on first HDR_FIELDS bytes)
    stored_hcrc = struct.unpack_from("<H", data, HDR_FIELDS)[0]
    if stored_hcrc != _crc16(data[:HDR_FIELDS]):
        return None

    total = HDR_TOTAL + plen + 4
    if len(data) < total:
        return None

    payload = data[HDR_TOTAL:HDR_TOTAL + plen]
    stored_pcrc = struct.unpack_from("<I", data, HDR_TOTAL + plen)[0]

    if plen > 0 and stored_pcrc != _crc32(payload):
        return None

    return Frame(type=msg_type, sequence=seq, flags=flags, payload=payload)


def find_frame_boundary(buffer: bytearray) -> Optional[int]:
    """Find start of next frame in byte stream; returns offset or None"""
    magic_bytes = struct.pack("<H", MAGIC)
    pos = buffer.find(magic_bytes)
    return pos if pos >= 0 else None


# --- Payload builders ---------------------------------------------------

def build_mouse_move(dx: int, dy: int, coalesced: int = 0) -> Frame:
    return Frame(type=MsgType.MOUSE_MOVE,
                 payload=struct.pack("<hhBB", dx, dy, coalesced, 0))

def build_mouse_button(button: int, action: int, buttons_state: int = 0) -> Frame:
    return Frame(type=MsgType.MOUSE_BUTTON,
                 payload=struct.pack("<BBBB", button, action, buttons_state, 0))

def build_mouse_wheel(delta: int, horizontal: int = 0) -> Frame:
    return Frame(type=MsgType.MOUSE_WHEEL,
                 payload=struct.pack("<hBB", delta, horizontal, 0))

def build_heartbeat() -> Frame:
    return Frame(type=MsgType.HEARTBEAT)

def build_heartbeat_ack() -> Frame:
    return Frame(type=MsgType.HEARTBEAT_ACK)

def build_control_enter() -> Frame:
    return Frame(type=MsgType.CONTROL_ENTER)

def build_control_leave() -> Frame:
    return Frame(type=MsgType.CONTROL_LEAVE)

# --- Payload parsers ----------------------------------------------------

def parse_mouse_move(frame: Frame) -> Tuple[int, int, int]:
    dx, dy, coalesced, _ = struct.unpack("<hhBB", frame.payload)
    return dx, dy, coalesced

def parse_mouse_button(frame: Frame) -> Tuple[int, int, int]:
    btn, action, state, _ = struct.unpack("<BBBB", frame.payload)
    return btn, action, state

def parse_mouse_wheel(frame: Frame) -> Tuple[int, int]:
    delta, horiz, _ = struct.unpack("<hBB", frame.payload)
    return delta, horiz
