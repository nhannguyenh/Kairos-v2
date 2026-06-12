"""
thuc_thi_lenh/quan_ly_lenh.py – State management lệnh & UI signals
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Trung tâm lưu trữ trạng thái runtime cho cả chế độ realtime và demo:
  • danh_sach_lenh_dang_chay – dict {symbol: order_info} persist qua JSON
  • data_lenh_dang_chay      – dict {symbol: multi-TF DataFrames} cho UI chart
  • data_lich_su             – list 100 lệnh đã đóng gần nhất

PyQt6 signal `ui_signals.data_changed` được emit mỗi khi state thay đổi
→ GUI tự cập nhật mà không cần polling.
"""

import json
import os
import time
from utils.log import logger
from PyQt6.QtCore import QObject, pyqtSignal


class SignalManager(QObject):
    """PyQt6 signal emitter – thread-safe bridge từ trading thread sang GUI thread."""

    data_changed = pyqtSignal(dict)


ui_signals = SignalManager()
# --- ĐƯỜNG DẪN FILE ---
FILE_REALTIME = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "du_lieu",
    "thong_tin_lenh",
    "trang_thai_lenh_realtime.json",
)
FILE_DEMO = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "du_lieu",
    "thong_tin_lenh",
    "trang_thai_lenh_demo.json",
)

FILE_LICH_SU_REALTIME = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "du_lieu",
    "thong_tin_lenh",
    "lich_su_lenh_realtime.json",
)
FILE_LICH_SU_DEMO = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "du_lieu",
    "thong_tin_lenh",
    "lich_su_lenh_demo.json",
)

# --- BIẾN TOÀN CỤC ---
danh_sach_lenh_dang_chay = {}
data_lenh_dang_chay = {}
data_lich_su = []
lich_su_dong_lenh = {}  # Lưu thời gian đóng lệnh gần nhất: {symbol: timestamp}

MAX_CANDLES_MEMORY = 300
total_lenh_lich_su = 100


def get_all_data():
    """Hàm gom toàn bộ dữ liệu hiện tại để gửi đi."""
    return {
        "lenh_dang_chay": danh_sach_lenh_dang_chay,
        "data_lenh_dang_chay": data_lenh_dang_chay,
        "lich_su": list(data_lich_su),
    }


def load_trang_thai(CHUC_NANG):
    """Load dữ liệu từ file vào RAM, hỗ trợ chế độ 'realtime' hoặc 'demo'."""
    if CHUC_NANG == "realtime":
        file_dang_chay = FILE_REALTIME
        file_lich_su = FILE_LICH_SU_REALTIME
    elif CHUC_NANG == "demo":
        file_dang_chay = FILE_DEMO
        file_lich_su = FILE_LICH_SU_DEMO
    else:
        return

    # 1. Load lệnh đang chạy
    if os.path.exists(file_dang_chay):
        try:
            with open(file_dang_chay, "r", encoding="utf-8") as f:
                data = json.load(f)
                danh_sach_lenh_dang_chay.clear()
                danh_sach_lenh_dang_chay.update(data)
            logger.info(
                f"[{CHUC_NANG}] Đã khôi phục {len(danh_sach_lenh_dang_chay)} lệnh đang treo."
            )
        except Exception as e:
            logger.error(f"Lỗi load đang chạy: {e}")

    # 2. Load lịch sử
    if os.path.exists(file_lich_su):
        try:
            with open(file_lich_su, "r", encoding="utf-8") as f:
                lines = f.readlines()

            last_100 = lines[-100:] if len(lines) > 100 else lines

            data_lich_su.clear()  # Xóa dữ liệu cũ

            for line in last_100:
                line = line.strip()
                if not line:
                    continue
                try:
                    order = json.loads(line)
                    data_lich_su.append(order)  # Append vào List
                except:
                    continue

            logger.info(f"[{CHUC_NANG}] Đã khôi phục {len(data_lich_su)} dòng lịch sử.")
        except Exception as e:
            logger.error(f"Lỗi load lịch sử: {e}")

    ui_signals.data_changed.emit(get_all_data())


def lich_su_lenh(CHUC_NANG, order_info):
    """Ghi thêm một lệnh đã đóng vào lịch sử RAM và file JSON."""
    if CHUC_NANG == "realtime":
        file_path = FILE_LICH_SU_REALTIME
    elif CHUC_NANG == "demo":
        file_path = FILE_LICH_SU_DEMO
    else:
        return

    data_lich_su.append(order_info)

    while len(data_lich_su) > total_lenh_lich_su:
        data_lich_su.pop(0)

    try:
        with open(file_path, "a", encoding="utf-8") as f:
            json_line = json.dumps(order_info, ensure_ascii=False)
            f.write(json_line + "\n")
        ui_signals.data_changed.emit(get_all_data())
    except Exception as e:
        if "logger" in globals():
            logger.error(f"Lỗi ghi file lịch sử ({CHUC_NANG}): {e}")
        else:
            print(f"Lỗi: {e}")


def save_trang_thai(CHUC_NANG):
    """Lưu danh sách lệnh đang chạy xuống file JSON tương ứng với chế độ."""
    if CHUC_NANG == "realtime":
        file_path = FILE_REALTIME
    elif CHUC_NANG == "demo":
        file_path = FILE_DEMO
    else:
        return

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(danh_sach_lenh_dang_chay, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Lỗi lưu file trạng thái: {e}")


def luu_lenh_moi(CHUC_NANG, symbol, order_info):
    """Lưu lệnh mới vào RAM và file, sau đó emit signal cập nhật UI."""
    danh_sach_lenh_dang_chay[symbol] = order_info
    save_trang_thai(CHUC_NANG)
    ui_signals.data_changed.emit(get_all_data())


def xoa_lenh(CHUC_NANG, symbol):
    """Xóa lệnh khỏi RAM và file khi vị thế được đóng."""
    if symbol in danh_sach_lenh_dang_chay:
        del danh_sach_lenh_dang_chay[symbol]

        if symbol in data_lenh_dang_chay:
            del data_lenh_dang_chay[symbol]

        # Ghi nhận thời điểm đóng lệnh để tính cooldown
        lich_su_dong_lenh[symbol] = time.time()

        save_trang_thai(CHUC_NANG)
        ui_signals.data_changed.emit(get_all_data())


def kiem_tra_cooldown(symbol, giay_cooldown=300):
    """
    Kiểm tra xem symbol có đang trong thời gian cooldown hay không.
    Trả về (True, thoi_gian_con_lai) nếu đang cooldown, ngược lại (False, 0).
    """
    last_close = lich_su_dong_lenh.get(symbol)
    if last_close is None:
        return False, 0
    elapsed = time.time() - last_close
    if elapsed < giay_cooldown:
        return True, giay_cooldown - elapsed
    return False, 0


def lay_thong_tin_lenh(symbol):
    """Lấy thông tin lệnh đang chạy theo symbol, trả về None nếu không tồn tại."""
    return danh_sach_lenh_dang_chay.get(symbol)


def kiem_tra_ton_tai(symbol):
    """Kiểm tra xem symbol có đang có lệnh mở hay không."""
    return symbol in danh_sach_lenh_dang_chay


def lay_danh_sach_symbol_dang_co():
    """Trả về danh sách tất cả symbol đang có vị thế mở."""
    return list(danh_sach_lenh_dang_chay.keys())


def data_vi_the_update(
    symbol, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d
):
    """Cập nhật dữ liệu đa khung cho một vị thế và emit signal UI."""
    data_lenh_dang_chay[symbol] = {
        "df_1m": df_1m.tail(MAX_CANDLES_MEMORY).clone(),
        "df_3m": df_3m.tail(MAX_CANDLES_MEMORY).clone(),
        "df_5m": df_5m.tail(MAX_CANDLES_MEMORY).clone(),
        "df_15m": df_15m.tail(MAX_CANDLES_MEMORY).clone(),
        "df_30m": df_30m.tail(MAX_CANDLES_MEMORY).clone(),
        "df_1h": df_1h.tail(MAX_CANDLES_MEMORY).clone(),
        "df_4h": df_4h.tail(MAX_CANDLES_MEMORY).clone(),
        "df_1d": df_1d.tail(MAX_CANDLES_MEMORY).clone(),
    }

    ui_signals.data_changed.emit(get_all_data())
    return data_lenh_dang_chay[symbol]


def xoa_bien_theo_symbol(symbol):
    """Xóa toàn bộ dữ liệu RAM liên quan đến một symbol và emit signal UI."""
    if symbol in danh_sach_lenh_dang_chay:
        del danh_sach_lenh_dang_chay[symbol]
    if symbol in data_lenh_dang_chay:
        del data_lenh_dang_chay[symbol]
    ui_signals.data_changed.emit(get_all_data())
