"""
chien_luoc/logic_bar_to_bar/quan_ly_chien_luoc.py – Điều phối chiến lược
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tầng trung gian giữa ML state prediction và các chiến lược cụ thể.
Luồng xử lý:
  1. Gọi phan_tich_trang_thai_thi_truong() để lấy ML regime hiện tại
  2. Route sang chiến lược tương ứng (Breakout / Reversion / Scalping / ...)
  3. Chỉ mở lệnh nếu điểm tín hiệu >= 20 (ngưỡng xác nhận đa khung)

Tương tự cho thoát lệnh: mỗi chiến lược có logic thoát riêng,
bot thoát khi tín hiệu đảo chiều đủ mạnh.
"""

from utils.log import logger
from logic_bar_to_bar.chien_luoc.chien_luoc_breakout import (
    phan_tich_breakout,
    thoat_breakout,
)
from logic_bar_to_bar.chien_luoc.chien_luoc_mean_reversion import (
    phan_tich_reversion,
    thoat_reversion,
)
from logic_bar_to_bar.chien_luoc.chien_luoc_scalping import (
    phan_tich_scalping,
    thoat_scalping,
)
from logic_bar_to_bar.chien_luoc.chien_luoc_squeeze import (
    phan_tich_squeeze,
    thoat_squeeze,
)
from logic_bar_to_bar.chien_luoc.chien_luoc_theo_trend_following import (
    phan_tich_theo_trend,
    thoat_theo_trend,
)

from logic_bar_to_bar.chien_luoc_trang_thai_thi_truong import (
    phan_tich_trang_thai_thi_truong,
)
from lay_du_lieu.lay_marketsnapshot import mo_theo_doi, dong_theo_doi
from lay_du_lieu.lay_macro import lay_du_lieu_io, lay_du_lieu_cam_xuc


# df_1m có 300 nến, df_3m có 100 nến, df_5m có 300 nến, df_15m có 100 nến, df_30m có 300 nến, df_1h có 150 nến, df_4h có 300 nến, df_1d có 50 nến
def chien_luoc_vao_lenh(
    symbol,
    Datetime,
    df_1m,
    df_3m,
    df_5m,
    df_15m,
    df_30m,
    df_1h,
    df_4h,
    df_1d,
    MarketSnapshot=None,
):
    """Entry point cho mỗi lần quét. Trả về (tin_hieu, diem, chien_luoc, ly_do, packet_ml)."""

    cho_phep, packet = phan_tich_trang_thai_thi_truong(
        symbol, Datetime, df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h
    )

    if not cho_phep:
        return None, 0, None, "Filter: Cấm trade", None

    if packet is None:
        return None, 0, None, "AI: Không đủ dữ liệu / Lỗi Model", None

    chien_luoc = packet["strategy_name"]

    tin_hieu, diem, ly_do = None, 0, []

    if chien_luoc == "Breakout":
        tin_hieu, diem, ly_do = phan_tich_breakout(
            symbol,
            df_1m,
            df_3m,
            df_5m,
            df_15m,
            df_30m,
            df_1h,
            df_4h,
            df_1d,
            MarketSnapshot,
        )
        if tin_hieu and abs(diem) >= 20:
            return tin_hieu, diem, chien_luoc, ly_do, packet

    elif chien_luoc == "Mean_reversion":
        tin_hieu, diem, ly_do = phan_tich_reversion(
            symbol,
            df_1m,
            df_3m,
            df_5m,
            df_15m,
            df_30m,
            df_1h,
            df_4h,
            df_1d,
            MarketSnapshot,
        )
        if tin_hieu and abs(diem) >= 20:
            return tin_hieu, diem, chien_luoc, ly_do, packet

    elif chien_luoc == "Scalping":
        tin_hieu, diem, ly_do = phan_tich_scalping(
            symbol,
            df_1m,
            df_3m,
            df_5m,
            df_15m,
            df_30m,
            df_1h,
            df_4h,
            df_1d,
            MarketSnapshot,
        )
        if tin_hieu and abs(diem) >= 20:
            return tin_hieu, diem, chien_luoc, ly_do, packet

    elif chien_luoc == "Squeeze":
        tin_hieu, diem, ly_do = phan_tich_squeeze(
            symbol,
            df_1m,
            df_3m,
            df_5m,
            df_15m,
            df_30m,
            df_1h,
            df_4h,
            df_1d,
            MarketSnapshot,
        )
        if tin_hieu and abs(diem) >= 20:
            return tin_hieu, diem, chien_luoc, ly_do, packet

    elif chien_luoc == "Trend_following":
        tin_hieu, diem, ly_do = phan_tich_theo_trend(
            symbol,
            df_1m,
            df_3m,
            df_5m,
            df_15m,
            df_30m,
            df_1h,
            df_4h,
            df_1d,
            MarketSnapshot,
        )
        if tin_hieu and abs(diem) >= 20:
            return tin_hieu, diem, chien_luoc, ly_do, packet

    return None, 0, None, None, None


# df_1m có 300 nến, df_3m có 100 nến, df_5m có 300 nến, df_15m có 100 nến, df_30m có 300 nến, df_1h có 150 nến, df_4h có 300 nến, df_1d có 50 nến
def chien_luoc_thoat_lenh(
    symbol,
    vi_the_hien_tai,
    chien_luoc,
    df_1m,
    df_3m,
    df_5m,
    df_15m,
    df_30m,
    df_1h,
    df_4h,
    df_1d,
    MarketSnapshot=None,
):
    """Kiểm tra tín hiệu đảo chiều. Trả về (True, lý_do) nếu nên đóng lệnh theo chiến lược."""

    vi_the = vi_the_hien_tai.lower()
    THRESHOLD_EXIT = 10

    if chien_luoc == "Breakout":
        th_breakout, diem_breakout, ly_do_breakout = thoat_breakout(
            df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d, MarketSnapshot
        )
        if vi_the == "buy":
            if th_breakout == "sell" and abs(diem_breakout) >= THRESHOLD_EXIT:
                return True, ly_do_breakout
        elif vi_the == "sell":
            if th_breakout == "buy" and abs(diem_breakout) >= THRESHOLD_EXIT:
                return True, ly_do_breakout

    elif chien_luoc == "Mean_reversion":
        th_reversion, diem_reversion, ly_do_reversion = thoat_reversion(
            df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d, MarketSnapshot
        )
        if vi_the == "buy":
            if th_reversion == "sell" and abs(diem_reversion) >= THRESHOLD_EXIT:
                return True, ly_do_reversion
        elif vi_the == "sell":
            if th_reversion == "buy" and abs(diem_reversion) >= THRESHOLD_EXIT:
                return True, ly_do_reversion

    elif chien_luoc == "Squeeze":
        th_squeeze, diem_squeeze, ly_do_squeeze = thoat_squeeze(
            df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d, MarketSnapshot
        )
        if vi_the == "buy":
            if th_squeeze == "sell" and abs(diem_squeeze) >= THRESHOLD_EXIT:
                return True, ly_do_squeeze
        elif vi_the == "sell":
            if th_squeeze == "buy" and abs(diem_squeeze) >= THRESHOLD_EXIT:
                return True, ly_do_squeeze

    elif chien_luoc == "Scalping":
        th_scalping, diem_scalping, ly_do_scalping = thoat_scalping(
            df_1m,
            df_3m,
            df_5m,
            df_15m,
            df_30m,
            df_1h,
            df_4h,
            df_1d,
            MarketSnapshot,
            vi_the=vi_the,
        )
        if vi_the == "buy":
            if th_scalping == "sell" and abs(diem_scalping) >= THRESHOLD_EXIT:
                return True, ly_do_scalping
        elif vi_the == "sell":
            if th_scalping == "buy" and abs(diem_scalping) >= THRESHOLD_EXIT:
                return True, ly_do_scalping

    elif chien_luoc == "Trend_following":
        th_theo_trend, diem_theo_trend, ly_do_theo_trend = thoat_theo_trend(
            df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d, MarketSnapshot
        )
        if vi_the == "buy":
            if th_theo_trend == "sell" and abs(diem_theo_trend) >= THRESHOLD_EXIT:
                return True, ly_do_theo_trend
        elif vi_the == "sell":
            if th_theo_trend == "buy" and abs(diem_theo_trend) >= THRESHOLD_EXIT:
                return True, ly_do_theo_trend

    return False, "Giữ lệnh"
