"""
chien_luoc/logic_bar_to_bar/chien_luoc/chien_luoc_mean_reversion.py – Đảo chiều về trung bình
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Logic: Giá đã chạy quá xa → kiệt sức → quay về trung bình.
Điều kiện vào lệnh:
  • RSI quá mua (>70) hoặc quá bán (<30)
  • Giá vượt ngoài dải Bollinger
  • Volume đột biến tại vùng cực trị (xác nhận dòng tiền xả/gom)

Dùng khi ML phát hiện: Cao_Trào (state 4) hoặc Hồi_Quy (state 5).
Khung tham chiếu chính: 1H (weight 5), phụ trợ 15M (3) và 5M (2).
"""

from joblib import Parallel, delayed
from logic_bar_to_bar.phan_tich_ky_thuat.khoi_luong import pt_volume
from logic_bar_to_bar.phan_tich_ky_thuat.xu_huong import pt_ema_trend
from logic_bar_to_bar.phan_tich_ky_thuat.bien_dong import (
    pt_bollinger_squeeze,
)
from logic_bar_to_bar.phan_tich_ky_thuat.dong_luong_dao_chieu import pt_rsi


def _tinh_diem_reversion(df, name, weight):
    """Tính điểm đảo chiều cho một khung thời gian (Polars DataFrame)."""
    if df is None or df.height < 30:
        return 0, ""

    rsi = pt_rsi(df)
    bb = pt_bollinger_squeeze(df)
    vol = pt_volume(df)
    ema = pt_ema_trend(df)

    last = df.tail(1).to_dicts()[0]
    price_now = last["close"]

    diem = 0
    ly_do = ""

    # --- TÌM ĐỈNH ĐỂ BÁN (Kiệt sức TĂNG) ---
    if rsi["muc_do"] == "QUÁ_MUA" and ema["trang_thai"] == "TĂNG":
        d = 2
        if price_now > bb["upper_band"]:
            d += 2  # giá vượt dải trên BB → tín hiệu rõ
        if vol["trang_thai"] == "DOT_BIEN":
            d += 2  # volume đột biến tại đỉnh → dấu hiệu xả hàng
        diem -= d * weight
        if d >= 2:
            ly_do = f"{name}: Kiệt sức TĂNG – RSI={rsi['rsi_val']:.1f}, Vol={vol['trang_thai']}"

    # --- TÌM ĐÁY ĐỂ MUA (Kiệt sức GIẢM) ---
    elif rsi["muc_do"] == "QUÁ_BÁN" and ema["trang_thai"] == "GIẢM":
        d = 2
        if price_now < bb["lower_band"]:
            d += 2  # giá thủng dải dưới BB
        if vol["trang_thai"] == "DOT_BIEN":
            d += 2  # volume đột biến tại đáy → dấu hiệu gom hàng
        diem += d * weight
        if d >= 2:
            ly_do = f"{name}: Kiệt sức GIẢM – RSI={rsi['rsi_val']:.1f}, Vol={vol['trang_thai']}"

    return diem, ly_do


def phan_tich_reversion(
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
    """Phân tích đảo chiều đa khung. Trả về (tin_hieu, diem, ly_do)."""
    cau_hinh_khung = [
        (df_1h, "1H", 5),
        (df_15m, "15M", 3),
        (df_5m, "5M", 2),
        (df_4h, "4H", 2),  # xác nhận macro
    ]

    ket_qua = Parallel(n_jobs=-1, prefer="threads")(
        delayed(_tinh_diem_reversion)(df, name, w) for df, name, w in cau_hinh_khung
    )

    tong_diem = sum(r[0] for r in ket_qua)
    ly_do = " | ".join(r[1] for r in ket_qua if r[1])

    # OrderFlow: nếu delta mua mạnh nhưng tín hiệu muốn bán → lọc bỏ
    if MarketSnapshot:
        delta = MarketSnapshot.get("delta", 0)
        imbalance = MarketSnapshot.get("imbalance", 0)
        if tong_diem <= -12 and delta > 500:
            tong_diem += 8
            ly_do += " | Flow chống SELL"
        elif tong_diem >= 12 and delta < -500:
            tong_diem -= 8
            ly_do += " | Flow chống BUY"

    NGUONG = 20
    tin_hieu = (
        "buy" if tong_diem >= NGUONG else "sell" if tong_diem <= -NGUONG else None
    )

    return tin_hieu, round(tong_diem, 2), ly_do


def thoat_reversion(
    df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d, MarketSnapshot=None
):
    """Thoát lệnh mean-reversion khi RSI về vùng trung tính hoặc giá quay lại giữa dải Bollinger."""
    if df_1h is None or df_1h.height < 20:
        return None, 0, "Thiếu dữ liệu"

    rsi_1h = pt_rsi(df_1h)
    bb_1h = pt_bollinger_squeeze(df_1h)
    rsi_5m = pt_rsi(df_5m) if df_5m is not None and df_5m.height >= 20 else rsi_1h

    last = df_1h.tail(1).to_dicts()[0]
    price_now = last["close"]
    mid_band = bb_1h.get("mid_band", price_now)

    # Tín hiệu thoát: giá đã về vùng trung bình
    if 40 <= rsi_1h["rsi_val"] <= 60:
        # RSI về trung tính = đảo chiều đã hoàn thành
        if price_now >= mid_band * 0.998 and rsi_5m["trang_thai"] != "YẾU":
            return (
                "buy",
                20,
                f"RSI về trung tính ({rsi_1h['rsi_val']:.1f}), giá chạm mid BB",
            )
        if price_now <= mid_band * 1.002 and rsi_5m["trang_thai"] != "MẠNH":
            return (
                "sell",
                -20,
                f"RSI về trung tính ({rsi_1h['rsi_val']:.1f}), giá chạm mid BB",
            )

    return None, 0, "Giữ lệnh"
