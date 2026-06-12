"""
chien_luoc/logic_bar_to_bar/chien_luoc/chien_luoc_breakout.py – Chiến lược Breakout
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phân tích 8 khung thời gian song song (joblib) với trọng số khác nhau:
  1m/3m/5m = weight 1  (noise filter)
  15m/30m  = weight 2  (confirmation)
  1h       = weight 5  (primary signal)
  4h/1d    = weight 3  (macro trend)

Tín hiệu = buy nếu tổng điểm >= 25, sell nếu <= -25.
OrderFlow (CVD + imbalance từ WebSocket) dùng để xác nhận hoặc lọc ngược chiều.
"""

import polars as pl
from utils.log import logger
from joblib import Parallel, delayed

# Các hàm phân tích kỹ thuật nhận Polars DataFrame
from logic_bar_to_bar.phan_tich_ky_thuat.cau_truc_gia import pt_breakout
from logic_bar_to_bar.phan_tich_ky_thuat.khoi_luong import pt_volume
from logic_bar_to_bar.phan_tich_ky_thuat.xu_huong import pt_adx
from logic_bar_to_bar.phan_tich_ky_thuat.bien_dong import pt_atr


def xu_ly_don_vi_khung(df, name, weight):
    """Tính điểm breakout cho một khung thời gian (Polars DataFrame)."""
    # 1. BẢO VỆ DỮ LIỆU: Polars dùng .height thay vì len()
    if df is None or df.height < 30:
        return 0, ""

    try:
        # Các hàm này phải là bản nhận Polars DataFrame và trả về dict
        brk = pt_breakout(df, window=20)
        vol = pt_volume(df)
        adx = pt_adx(df)
        atr = pt_atr(df)

        # 2. XỬ LÝ AN TOÀN
        adx_val = adx.get("adx_val", 0) if isinstance(adx, dict) else 0
        vol_status = vol.get("trang_thai", "") if isinstance(vol, dict) else ""
        brk_status = brk.get("trang_thai", "") if isinstance(brk, dict) else ""
        atr_status = atr.get("trang_thai", "") if isinstance(atr, dict) else ""

        diem = 0
        ly_do = ""

        # Logic tính điểm Bullish
        if brk_status == "BREAK_OUT":
            diem_cong = 1
            if vol_status in ["TANG", "DOT_BIEN"]:
                diem_cong += 2
            if adx_val > 25:
                diem_cong += 1
            if atr_status == "BIẾN_ĐỘNG_CAO":
                diem_cong += 1
            diem += diem_cong * weight
            ly_do = f"{name}: Phá đỉnh (Vol: {vol_status})"

        elif brk_status == "BREAK_DOWN":
            diem_tru = 1
            if vol_status in ["TANG", "DOT_BIEN"]:
                diem_tru += 2
            if adx_val > 25:
                diem_tru += 1
            if atr_status == "BIẾN_ĐỘNG_CAO":
                diem_tru += 1
            diem -= diem_tru * weight
            ly_do = f"{name}: Phá gáy (Vol: {vol_status})"

        return diem, ly_do

    except Exception as e:
        logger.error(f"Lỗi xử lý khung {name}: {e}")
        return 0, ""


def phan_tich_breakout(
    symbol,
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
    """Phân tích breakout đa khung song song. Trả về (tin_hieu, diem, ly_do)."""
    cau_hinh_khung = [
        (df_1m, "1M", 1),
        (df_3m, "3M", 1),
        (df_5m, "5M", 1),
        (df_15m, "15M", 2),
        (df_30m, "30M", 2),
        (df_1h, "1H", 5),
        (df_4h, "4H", 3),
        (df_1d, "1D", 1),
    ]

    ket_qua = Parallel(
        n_jobs=-1, prefer="threads"
    )(  # Dùng "threads" cho Polars thường tốt hơn
        delayed(xu_ly_don_vi_khung)(df, name, weight)
        for df, name, weight in cau_hinh_khung
    )

    tong_diem = sum(res[0] for res in ket_qua)
    cac_ly_do = [res[1] for res in ket_qua if res[1] != ""]

    nguong_xac_nhan = 25

    if MarketSnapshot:
        delta = MarketSnapshot.get("delta", 0)
        imbalance = MarketSnapshot.get("imbalance", 0)

        if tong_diem >= nguong_xac_nhan:
            if delta > 0 and imbalance > 0.1:
                tong_diem += 5
                cac_ly_do.append("OrderFlow xác nhận BUY")
            else:
                tong_diem -= 10
                cac_ly_do.append("Flow không ủng hộ BUY")

        elif tong_diem <= -nguong_xac_nhan:
            if delta < 0 and imbalance < -0.1:
                tong_diem -= 5
                cac_ly_do.append("OrderFlow xác nhận SELL")
            else:
                tong_diem += 10
                cac_ly_do.append("Flow không ủng hộ SELL")

    tin_hieu = (
        "buy"
        if tong_diem >= nguong_xac_nhan
        else "sell" if tong_diem <= -nguong_xac_nhan else None
    )

    return tin_hieu, round(tong_diem, 2), "; ".join(cac_ly_do)


def thoat_breakout(
    df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d, MarketSnapshot=None
):
    """Kiểm tra tín hiệu đảo chiều breakout để quyết định thoát lệnh. Trả về (tin_hieu, diem, ly_do)."""
    cau_hinh_khung = [
        (df_1m, "1M", 1),
        (df_3m, "3M", 1),
        (df_5m, "5M", 1),
        (df_15m, "15M", 2),
        (df_30m, "30M", 2),
        (df_1h, "1H", 5),
        (df_4h, "4H", 3),
        (df_1d, "1D", 3),
    ]

    ket_qua = Parallel(n_jobs=-1)(
        delayed(xu_ly_don_vi_khung)(df, name, weight)
        for df, name, weight in cau_hinh_khung
    )

    tong_diem = sum(res[0] for res in ket_qua)
    cac_ly_do = [res[1] for res in ket_qua if res[1] != ""]

    if MarketSnapshot:
        delta = MarketSnapshot.get("delta", 0)
        imbalance = MarketSnapshot.get("imbalance", 0)
        if tong_diem < 0 and (delta < -500 or imbalance < -0.2):
            tong_diem -= 5
            cac_ly_do.append("OrderFlow xác nhận áp lực BÁN")
        elif tong_diem > 0 and (delta > 500 or imbalance > 0.2):
            tong_diem += 5
            cac_ly_do.append("OrderFlow xác nhận áp lực MUA")

    tin_hieu_thi_truong = (
        "buy" if tong_diem >= 15 else "sell" if tong_diem <= -15 else None
    )

    return tin_hieu_thi_truong, round(tong_diem, 2), "; ".join(cac_ly_do)
