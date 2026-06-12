"""
chien_luoc/logic_bar_to_bar/chien_luoc/chien_luoc_scalping.py – Scalping nhanh
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Logic: Vào/thoát nhanh khi giá chạm biên dao động.
  • RSI extreme (<35 hoặc >65) tại biên Bollinger Bands
  • Volume xác nhận (không vào khi vol quá thấp)
  • Chỉ dùng khung ngắn: 1M (weight 4), 3M (3), 5M (2)
  • OrderFlow: imbalance order book xác nhận áp lực mua/bán

Dùng khi ML phát hiện: Nhiễu_Động (state 6) – thị trường đi ngang biên độ hẹp.
"""

from joblib import Parallel, delayed
from logic_bar_to_bar.phan_tich_ky_thuat.dong_luong_dao_chieu import pt_rsi
from logic_bar_to_bar.phan_tich_ky_thuat.bien_dong import (
    pt_bollinger_squeeze,
)
from logic_bar_to_bar.phan_tich_ky_thuat.khoi_luong import pt_volume


def _tinh_diem_scalp(df, name, weight):
    """Tính điểm scalp cho một khung ngắn (Polars DataFrame)."""
    if df is None or df.height < 25:
        return 0, ""

    rsi = pt_rsi(df)
    bb = pt_bollinger_squeeze(df)
    vol = pt_volume(df)

    last = df.tail(1).to_dicts()[0]
    price_now = last["close"]

    # Không scalp khi volume quá thấp (thanh khoản cạn)
    if vol["trang_thai"] == "THAP":
        return 0, ""

    diem = 0
    ly_do = ""

    # --- LONG SCALP: giá chạm/dưới dải dưới BB + RSI quá bán ---
    if rsi["rsi_val"] < 35 and price_now <= bb["lower_band"] * 1.003:
        d = 3
        if price_now <= bb["lower_band"]:
            d += 2  # giá thực sự thủng dải dưới
        if vol["trang_thai"] == "DOT_BIEN":
            d += 1  # volume spike = có người gom
        diem += d * weight
        ly_do = f"{name}: RSI={rsi['rsi_val']:.1f} tại Lower BB → LONG scalp"

    # --- SHORT SCALP: giá chạm/trên dải trên BB + RSI quá mua ---
    elif rsi["rsi_val"] > 65 and price_now >= bb["upper_band"] * 0.997:
        d = 3
        if price_now >= bb["upper_band"]:
            d += 2  # giá thực sự vượt dải trên
        if vol["trang_thai"] == "DOT_BIEN":
            d += 1  # volume spike = có người xả
        diem -= d * weight
        ly_do = f"{name}: RSI={rsi['rsi_val']:.1f} tại Upper BB → SHORT scalp"

    return diem, ly_do


def phan_tich_scalping(
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
    """Phân tích scalp đa khung ngắn. Trả về (tin_hieu, diem, ly_do)."""
    cau_hinh_khung = [
        (df_1m, "1M", 4),  # khung 1m quan trọng nhất cho scalp
        (df_3m, "3M", 3),
        (df_5m, "5M", 2),
    ]

    ket_qua = Parallel(n_jobs=-1, prefer="threads")(
        delayed(_tinh_diem_scalp)(df, name, w) for df, name, w in cau_hinh_khung
    )

    tong_diem = sum(r[0] for r in ket_qua)
    ly_do = " | ".join(r[1] for r in ket_qua if r[1])

    # Lọc bằng 15M: nếu 15M đang trend mạnh, không scalp ngược chiều
    if df_15m is not None and df_15m.height >= 25:
        from logic_bar_to_bar.phan_tich_ky_thuat.xu_huong import (
            pt_ema_trend,
            pt_adx,
        )

        ema_15m = pt_ema_trend(df_15m)
        adx_15m = pt_adx(df_15m)
        if adx_15m["trang_thai"] == "CO_XU_HUONG" and adx_15m["adx_val"] > 35:
            # Trend mạnh → scalp ngược chiều rủi ro cao, giảm điểm
            if (tong_diem > 0 and ema_15m["trang_thai"] == "GIẢM") or (
                tong_diem < 0 and ema_15m["trang_thai"] == "TĂNG"
            ):
                tong_diem = int(tong_diem * 0.5)
                ly_do += f" | 15M trend mạnh ({ema_15m['trang_thai']}), giảm điểm"

    # OrderFlow: imbalance order book xác nhận áp lực tức thì
    if MarketSnapshot:
        imbalance = MarketSnapshot.get("imbalance", 0)
        delta = MarketSnapshot.get("delta", 0)
        if tong_diem > 0 and (imbalance > 0.15 or delta > 0):
            tong_diem += 4
            ly_do += " | OrderFlow hỗ trợ BUY"
        elif tong_diem < 0 and (imbalance < -0.15 or delta < 0):
            tong_diem -= 4
            ly_do += " | OrderFlow hỗ trợ SELL"

    NGUONG = 20
    tin_hieu = (
        "buy" if tong_diem >= NGUONG else "sell" if tong_diem <= -NGUONG else None
    )

    return tin_hieu, round(tong_diem, 2), ly_do


def thoat_scalping(
    df_1m,
    df_3m,
    df_5m,
    df_15m,
    df_30m,
    df_1h,
    df_4h,
    df_1d,
    MarketSnapshot=None,
    vi_the=None,
):
    """Thoát scalp nhanh khi RSI về trung tính (45-55) hoặc giá về mid Bollinger trên khung 1M/3M."""
    if df_1m is None or df_1m.height < 20:
        return None, 0, "Thiếu dữ liệu"

    rsi_1m = pt_rsi(df_1m)
    bb_1m = pt_bollinger_squeeze(df_1m)

    last = df_1m.tail(1).to_dicts()[0]
    price_now = last["close"]
    mid_band = bb_1m.get("mid_band", price_now)

    if vi_the is None:
        return None, 0, "Thiếu thông tin vị thế"
    tin_hieu_dong = "sell" if vi_the == "buy" else "buy"

    # RSI về trung tính = mục tiêu scalp đã đạt
    if 43 <= rsi_1m["rsi_val"] <= 57:
        return tin_hieu_dong, 20, f"RSI scalp về trung tính ({rsi_1m['rsi_val']:.1f})"

    # Giá về mid BB = thoát lấy lời
    if abs(price_now - mid_band) / (mid_band + 1e-9) < 0.002:
        return tin_hieu_dong, 15, "Giá về mid Bollinger"

    # OrderFlow đảo chiều đột ngột
    if MarketSnapshot:
        imbalance = MarketSnapshot.get("imbalance", 0)
        if abs(imbalance) > 0.3:
            tin_hieu = "buy" if imbalance > 0 else "sell"
            return tin_hieu, 20, f"Imbalance đảo chiều mạnh ({imbalance:.2f})"

    return None, 0, "Giữ lệnh"
