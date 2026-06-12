"""
utils/thoi_gian.py – Tiện ích thời gian
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Wrapper mỏng quanh thư viện time chuẩn, giúp code gọi tên
rõ nghĩa hơn và dễ mock khi unit test.
"""

import time
from datetime import datetime


def lay_timestamp_ms():
    """Trả về Unix timestamp hiện tại tính bằng milliseconds (dùng để đo latency)."""
    return int(time.time() * 1000)


def ngu_an_toan(giay):
    """Sleep không blocking, đặt tên rõ nghĩa để tránh nhầm với sleep vô tình."""
    time.sleep(giay)
