"""
chien_luoc/logic_bar_to_bar/chien_luoc_trang_thai_thi_truong.py – Bộ lọc thị trường
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cổng kiểm soát TRƯỚC khi vào bất kỳ chiến lược nào. 3 điều kiện phải pass:
  1. Thời gian hợp lệ (không cuối tuần, không 5h sáng – giờ giãn spread)
  2. Đủ dữ liệu khung 1h (>=120 nến) để ML có context
  3. ML model dự đoán được regime thị trường

Nếu bất kỳ điều kiện nào fail → trả về (False, lý_do) → bot không trade.
"""

import polars as pl
from logic_bar_to_bar.phan_tich_ky_thuat.chu_ky import (
    pt_kiem_tra_gio,
    pt_kiem_tra_ngay,
)
from ml.trang_thai_thi_truong_ml.ml_predict import du_doan_trang_thai_ml


def phan_tich_trang_thai_thi_truong(
    symbol, Datetime, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h
):
    """Kiểm tra bộ lọc thời gian, dữ liệu và ML trước khi cho phép vào lệnh. Trả về (cho_phep, packet)."""
    # 1. Kiểm tra điều kiện thời gian (Giữ nguyên vì dt là đối tượng đơn lẻ)
    kq_ngay = pt_kiem_tra_ngay(Datetime)
    kq_gio = pt_kiem_tra_gio(Datetime)

    if not (kq_ngay["trang_thai"] == "HỢP_LỆ" and kq_gio["trang_thai"] == "HỢP_LỆ"):
        ly_do = (
            kq_ngay["trang_thai"]
            if kq_ngay["trang_thai"] != "HỢP_LỆ"
            else kq_gio["trang_thai"]
        )
        return False, f"NGHỈ ({ly_do})"

    # 2. Kiểm tra độ dài dữ liệu (ML cần >= 120 nến 1H và >= 120 nến 4H)
    if df_1h is None or df_1h.height < 120:
        return False, "THIẾU_DỮ_LIỆU (1H)"
    if df_4h is None or df_4h.height < 60:
        return False, "THIẾU_DỮ_LIỆU (4H)"

    # 3. Dự đoán trạng thái bằng ML — đúng 4 khung thời gian mô hình yêu cầu
    packet = du_doan_trang_thai_ml(df_5m, df_15m, df_1h, df_4h)

    if packet is None:
        return False, "ML_DỰ_ĐOÁN_LỖI"

    return True, packet
