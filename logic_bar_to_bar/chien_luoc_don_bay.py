"""
chien_luoc/logic_bar_to_bar/chien_luoc_don_bay.py – Đòn bẩy động
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Điều chỉnh đòn bẩy trong khoảng [1, 50] dựa trên 4 chỉ báo khung 15m:
  • ATR cao + Volume đột biến → giảm đòn bẩy (tin mạnh, rủi ro cao)
  • ADX thấp + BB nén → giới hạn 10x (thị trường sideway tích lũy)
  • Breakout rõ + ADX > 25 → giữ nguyên đòn bẩy gốc
  • Mặc định → tăng/giảm 1x theo tỷ lệ ATR/ATR_mean
"""

import polars as pl
from utils.log import logger
from logic_bar_to_bar.phan_tich_ky_thuat.xu_huong import pt_adx
from logic_bar_to_bar.phan_tich_ky_thuat.khoi_luong import pt_volume
from logic_bar_to_bar.phan_tich_ky_thuat.cau_truc_gia import pt_breakout
from logic_bar_to_bar.phan_tich_ky_thuat.bien_dong import (
    pt_atr,
    pt_bollinger_squeeze,
)


def phan_tich_don_bay(
    symbol, don_bay, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d
):
    """Điều chỉnh đòn bẩy động theo điều kiện thị trường khung 15m. Trả về đòn bẩy mới."""
    # 1. KIỂM TRA DỮ LIỆU: Polars dùng .height thay vì len()
    # Khung 15m làm chuẩn cần tối thiểu khoảng 100 nến để các chỉ báo (ATR mean 100) không bị Null
    if df_15m is None or df_15m.height < 100:
        return don_bay

    # 2. TRÍCH XUẤT CHỈ BÁO
    adx = pt_adx(df_15m)
    vol = pt_volume(df_15m)
    brk = pt_breakout(df_15m)
    atr = pt_atr(df_15m, 14, 100)
    bb = pt_bollinger_squeeze(df_15m)

    # Bảo vệ: Nếu bất kỳ chỉ báo nào trả về None do lỗi tính toán
    if not all([adx, vol, brk, atr, bb]):
        return don_bay

    don_bay_moi = don_bay
    ly_do = ""

    # --- LOGIC ĐỊNH NGHĨA ĐIỀU KIỆN THỊ TRƯỜNG ---

    # 1. TIN MẠNH (High Volatility)
    if atr["trang_thai"] == "BIẾN_ĐỘNG_CAO" and vol["trang_thai"] == "DOT_BIEN":
        don_bay_moi -= 3
        ly_do = "TIN MẠNH => Biến động & Volume đột biến."

    # 2. SIDEWAY (Thị trường đi ngang, nén)
    elif adx["trang_thai"] == "SIDEWAY" and bb["trang_thai"] == "BOP":
        don_bay_moi = min(don_bay, 10)
        ly_do = "SIDEWAY => ADX thấp + BB bóp. Thị trường tích lũy."

    # 3. BREAKOUT RÕ (Xác nhận xu hướng)
    elif (
        brk["trang_thai"] != "KHONG"
        and adx["trang_thai"] == "CO_XU_HUONG"
        and vol["trang_thai"] != "THAP"
    ):
        don_bay_moi = don_bay
        ly_do = f"BREAKOUT => Brk {brk['trang_thai']}, Vol ổn định."

    # 4. LOGIC MẶC ĐỊNH
    else:
        # Sử dụng các giá trị float từ dict của Polars
        atr_val = atr.get("atr_val", 0)
        atr_mean = atr.get("atr_mean", 0)

        if atr_val > atr_mean * 1.05:
            don_bay_moi -= 1
            ly_do = "ATR > Mean 5%: Giảm nhẹ Leverage."
        elif atr_val < atr_mean * 0.95:
            don_bay_moi += 1
            ly_do = "ATR < Mean 5%: Tăng nhẹ Leverage."
        else:
            ly_do = "Thị trường ổn định."

    # Đảm bảo đòn bẩy hợp lệ
    don_bay_moi = int(max(1, min(50, don_bay_moi)))

    if don_bay_moi != don_bay:
        logger.info(
            f"[LEV    ] {symbol:<9}  {'LEV':<2} | "
            f"    {don_bay}x -> {don_bay_moi}x{'':<2}   | "
            f"R: {ly_do}"
        )

    return don_bay_moi
