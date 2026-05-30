"""
Protocol 编解码单元测试
"""
import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.shared.protocol import (
    Frame, MsgType, encode, decode, find_frame_boundary,
    build_mouse_move, build_mouse_button, build_mouse_wheel,
    build_heartbeat, build_control_enter, build_control_leave,
    parse_mouse_move, parse_mouse_button, parse_mouse_wheel,
)


class TestProtocol(unittest.TestCase):

    def test_encode_decode_mouse_move(self):
        frame = build_mouse_move(100, -50)
        frame.sequence = 42
        data = encode(frame)
        decoded = decode(data)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.type, MsgType.MOUSE_MOVE)
        self.assertEqual(decoded.sequence, 42)
        dx, dy, _ = parse_mouse_move(decoded)
        self.assertEqual(dx, 100)
        self.assertEqual(dy, -50)

    def test_encode_decode_mouse_button(self):
        frame = build_mouse_button(1, 1, 1)
        frame.sequence = 7
        data = encode(frame)
        decoded = decode(data)
        self.assertIsNotNone(decoded)
        btn, action, state = parse_mouse_button(decoded)
        self.assertEqual(btn, 1)
        self.assertEqual(action, 1)  # PRESS

    def test_encode_decode_mouse_wheel(self):
        frame = build_mouse_wheel(3)
        data = encode(frame)
        decoded = decode(data)
        delta, horiz = parse_mouse_wheel(decoded)
        self.assertEqual(delta, 3)
        self.assertEqual(horiz, 0)

    def test_heartbeat_frame(self):
        frame = build_heartbeat()
        data = encode(frame)
        decoded = decode(data)
        self.assertEqual(decoded.type, MsgType.HEARTBEAT)

    def test_control_frames(self):
        for builder, expected_type in [
            (build_control_enter, MsgType.CONTROL_ENTER),
            (build_control_leave, MsgType.CONTROL_LEAVE),
        ]:
            frame = builder()
            data = encode(frame)
            decoded = decode(data)
            self.assertEqual(decoded.type, expected_type)

    def test_find_boundary(self):
        buf = bytearray(b"garbage" + encode(build_heartbeat()) + b"more")
        pos = find_frame_boundary(buf)
        self.assertIsNotNone(pos)
        self.assertEqual(pos, 7)  # "garbage" = 7 bytes

    def test_partial_frame(self):
        frame = build_mouse_move(1, 2)
        data = encode(frame)
        # 只给一半数据
        result = decode(data[:10])
        self.assertIsNone(result)

    def test_corrupted_frame(self):
        frame = build_heartbeat()
        data = bytearray(encode(frame))
        data[5] ^= 0xFF  # 破坏一个字节
        result = decode(bytes(data))
        self.assertIsNone(result)

    def test_10000_roundtrip(self):
        """压力测试：10000 次编解码"""
        for i in range(10000):
            frame = build_mouse_move(i % 1000, -(i % 500))
            frame.sequence = i
            data = encode(frame)
            decoded = decode(data)
            self.assertIsNotNone(decoded, f"Roundtrip {i} failed")
            self.assertEqual(decoded.sequence, i)


if __name__ == "__main__":
    unittest.main()
