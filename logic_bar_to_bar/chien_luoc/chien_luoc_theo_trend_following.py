"""
chien_luoc/logic_bar_to_bar/chien_luoc/chien_luoc_theo_trend_following.py – Theo xu hướng
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Logic: Vào lệnh cùng chiều xu hướng khi các khung đồng thuận.
  • EMA hướng xác định chiều (TĂNG/GIẢM)
  • ATR cao → biến động đủ để chạy → tăng điểm
  • RSI hỗ trợ xu hướng (>50 TĂNG, <50 GIẢM)
  • Khung dài (1D/4H) trọng số cao hơn để lọc nhiễu ngắn hạn

Dùng khi ML phát hiện: Đầu_Xu_Hướng (state 2) hoặc Xu_Hướng_Mạnh (state 3).
"""

from joblib import Parallel, delayed
from logic_bar_to_bar.phan_tich_ky_thuat.bien_dong import pt_atr
from logic_bar_to_bar.phan_tich_ky_thuat.xu_huong import pt_ema_trend, pt_adx
from logic_bar_to_bar.phan_tich_ky_thuat.dong_luong_dao_chieu import pt_rsi


def _tinh_diem_trend(df, name, weight):
    """Tính điểm xu hướng cho một khung (Polars DataFrame)."""
    if df is None or df.height < 30:
        return 0, ""

    ema = pt_ema_trend(df)
    atr = pt_atr(df)
    rsi = pt_rsi(df)
    adx = pt_adx(df)

    if not all([ema, atr, rsi, adx]):
        return 0, ""

    diem = 0

    if ema["trang_thai"] == "TĂNG":
        diem += weight
        # Biến động cao = xu hướng có lực → cộng thêm
        if atr["trang_thai"] == "BIẾN_ĐỘNG_CAO":
            diem += weight * 0.5
        # RSI xác nhận đà tăng
        if rsi["trang_thai"] == "MẠNH":
            diem += weight * 0.3
        # ADX xác nhận xu hướng thật (không phải nhiễu)
        if adx["trang_thai"] == "CO_XU_HUONG":
            diem += weight * 0.5

    elif ema["trang_thai"] == "GIẢM":
        diem -= weight
        if atr["trang_thai"] == "BIẾN_ĐỘNG_CAO":
            diem -= weight * 0.5
        if rsi["trang_thai"] == "YẾU":
            diem -= weight * 0.3
        if adx["trang_thai"] == "CO_XU_HUONG":
            diem -= weight * 0.5

    ly_do = f"{name}: {ema['trang_thai']} | ADX={adx['adx_val']:.1f} | RSI={rsi['rsi_val']:.1f}"
    return diem, ly_do


def phan_tich_theo_trend(
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
    """Phân tích xu hướng đa khung. Trả về (tin_hieu, diem, ly_do)."""
    cau_hinh_khung = [
        (df_1d, "1D", 10),  # macro trend – quyết định chiều lớn
        (df_4h, "4H", 8),  # swing trend
        (df_1h, "1H", 5),  # intraday trend
        (df_15m, "15M", 3),
        (df_5m, "5M", 2),
    ]

    ket_qua = Parallel(n_jobs=-1, prefer="threads")(
        delayed(_tinh_diem_trend)(df, name, w) for df, name, w in cau_hinh_khung
    )

    tong_diem = sum(r[0] for r in ket_qua)
    ly_do = " | ".join(r[1] for r in ket_qua if r[1])

    # OrderFlow: CVD đồng thuận thì cộng điểm xác nhận
    if MarketSnapshot:
        delta = MarketSnapshot.get("delta", 0)
        imbalance = MarketSnapshot.get("imbalance", 0)
        if tong_diem > 0 and delta > 0 and imbalance > 0.1:
            tong_diem += 5
            ly_do += " | OrderFlow xác nhận BUY"
        elif tong_diem < 0 and delta < 0 and imbalance < -0.1:
            tong_diem -= 5
            ly_do += " | OrderFlow xác nhận SELL"

    NGUONG = 20
    tin_hieu = (
        "buy" if tong_diem >= NGUONG else "sell" if tong_diem <= -NGUONG else None
    )

    return tin_hieu, round(tong_diem, 2), ly_do


def thoat_theo_trend(
    df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d, MarketSnapshot=None
):
    """Thoát khi xu hướng suy yếu: EMA 1H lật chiều hoặc ADX giảm dưới 20."""
    if df_1h is None or df_1h.height < 30:
        return None, 0, "Thiếu dữ liệu"

    ema_1h = pt_ema_trend(df_1h)
    adx_1h = pt_adx(df_1h)
    ema_4h = pt_ema_trend(df_4h) if df_4h is not None and df_4h.height >= 30 else None

    ly_do_thoat = []
    diem_thoat = 0

    # EMA 1H đổi chiều → xu hướng chuyển sang giai đoạn khác
    if ema_1h["muc_do"] == "TỐT":
        diem_thoat += 10
        ly_do_thoat.append(f"EMA 1H đổi chiều: {ema_1h['trang_thai']}")

    # ADX thấp = xu hướng không còn lực
    if adx_1h["trang_thai"] == "SIDEWAY":
        diem_thoat += 8
        ly_do_thoat.append(f"ADX={adx_1h['adx_val']:.1f} – xu hướng tan rã")

    # Nếu 4H cũng đổi chiều thì chắc chắn hơn
    if ema_4h and ema_4h["muc_do"] == "TỐT":
        diem_thoat += 5
        ly_do_thoat.append(f"EMA 4H đổi chiều: {ema_4h['trang_thai']}")

    if diem_thoat >= 15:
        # Dùng EMA 1H để biết nên thoát về phía nào
        tin_hieu = "sell" if ema_1h["trang_thai"] == "TĂNG" else "buy"
        return tin_hieu, diem_thoat, " | ".join(ly_do_thoat)

    return None, 0, "Giữ lệnh"
