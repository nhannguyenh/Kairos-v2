"""
chien_luoc/logic_bar_to_bar/chien_luoc/chien_luoc_squeeze.py – Bứt phá sau nén chặt
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Logic: BB nén chặt (bandwidth < mean) → tích lũy năng lượng → bứt phá.
  1. Phát hiện squeeze: BB bandwidth < trung bình (trang_thai == 'BOP')
  2. Xác định chiều bứt phá: price action breakout + EMA hỗ trợ
  3. Squeeze càng chặt (muc_do == 'CHAT') → điểm nhân đôi
  4. Volume tăng khi bứt phá = xác nhận

Dùng khi ML phát hiện: Nén_Chặt (state 1).
Khung tham chiếu chính: 15M (5), 30M (4), 1H (3).
"""

from joblib import Parallel, delayed
from logic_bar_to_bar.phan_tich_ky_thuat.bien_dong import (
    pt_bollinger_squeeze,
)
from logic_bar_to_bar.phan_tich_ky_thuat.cau_truc_gia import pt_breakout
from logic_bar_to_bar.phan_tich_ky_thuat.khoi_luong import pt_volume
from logic_bar_to_bar.phan_tich_ky_thuat.xu_huong import pt_ema_trend


def _tinh_diem_squeeze(df, name, weight):
    """Tính điểm bứt phá squeeze cho một khung (Polars DataFrame)."""
    if df is None or df.height < 30:
        return 0, ""

    bb = pt_bollinger_squeeze(df)
    brk = pt_breakout(df)
    vol = pt_volume(df)
    ema = pt_ema_trend(df)

    # Chỉ áp dụng khi đang có squeeze
    if bb["trang_thai"] != "BOP":
        return 0, ""

    # Squeeze càng chặt (CHAT) thì nhân đôi điểm
    he_so = 2 if bb["muc_do"] == "CHAT" else 1

    diem = 0
    ly_do = ""

    # --- BỨT PHÁ TĂNG: price action + EMA cùng chiều ---
    if brk["trang_thai"] == "BREAK_OUT" and ema["trang_thai"] == "TĂNG":
        d = 3
        if vol["trang_thai"] in ["TANG", "DOT_BIEN"]:
            d += 2  # volume tăng = bứt phá thật, không phải fakeout
        diem += d * weight * he_so
        ly_do = f"{name}: Squeeze BỨT PHÁ TĂNG | BW={bb['bandwidth']:.4f} | Vol={vol['trang_thai']}"

    # --- BỨT PHÁ GIẢM ---
    elif brk["trang_thai"] == "BREAK_DOWN" and ema["trang_thai"] == "GIẢM":
        d = 3
        if vol["trang_thai"] in ["TANG", "DOT_BIEN"]:
            d += 2
        diem -= d * weight * he_so
        ly_do = f"{name}: Squeeze BỨT PHÁ GIẢM | BW={bb['bandwidth']:.4f} | Vol={vol['trang_thai']}"

    # --- SQUEEZE CHƯA BỨT PHÁ: tích điểm trung bình theo EMA ---
    else:
        # Dự đoán chiều từ EMA để chuẩn bị sẵn
        if ema["trang_thai"] == "TĂNG":
            diem += 1 * weight * he_so
        else:
            diem -= 1 * weight * he_so

    return diem, ly_do


def phan_tich_squeeze(
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
    """Phân tích squeeze đa khung. Trả về (tin_hieu, diem, ly_do)."""
    cau_hinh_khung = [
        (df_15m, "15M", 5),  # khung chính để phát hiện squeeze
        (df_30m, "30M", 4),
        (df_1h, "1H", 3),
        (df_5m, "5M", 2),  # xác nhận bứt phá ngắn hạn
    ]

    ket_qua = Parallel(n_jobs=-1, prefer="threads")(
        delayed(_tinh_diem_squeeze)(df, name, w) for df, name, w in cau_hinh_khung
    )

    tong_diem = sum(r[0] for r in ket_qua)
    ly_do = " | ".join(r[1] for r in ket_qua if r[1])

    # OrderFlow: khi squeeze nổ, delta CVD xác nhận lực mua/bán thật
    if MarketSnapshot:
        delta = MarketSnapshot.get("delta", 0)
        imbalance = MarketSnapshot.get("imbalance", 0)
        liq_long = MarketSnapshot.get("liq_long", 0)
        liq_short = MarketSnapshot.get("liq_short", 0)

        if tong_diem > 0:
            if delta > 0 and imbalance > 0.1:
                tong_diem += 5
                ly_do += " | CVD xác nhận BUY"
            elif liq_short > 0:
                tong_diem += 3  # short bị quét → lực tăng
                ly_do += " | Short squeeze xác nhận"

        elif tong_diem < 0:
            if delta < 0 and imbalance < -0.1:
                tong_diem -= 5
                ly_do += " | CVD xác nhận SELL"
            elif liq_long > 0:
                tong_diem -= 3  # long bị quét → lực giảm
                ly_do += " | Long squeeze xác nhận"

    NGUONG = 20
    tin_hieu = (
        "buy" if tong_diem >= NGUONG else "sell" if tong_diem <= -NGUONG else None
    )

    return tin_hieu, round(tong_diem, 2), ly_do


def thoat_squeeze(
    df_1m, df_3m, df_5m, df_15m, df_30m, df_1h, df_4h, df_1d, MarketSnapshot=None
):
    """Thoát squeeze khi BB mở rộng trở lại hoặc price action đảo chiều (breakout thất bại)."""
    if df_15m is None or df_15m.height < 30:
        return None, 0, "Thiếu dữ liệu"

    bb_15m = pt_bollinger_squeeze(df_15m)
    brk_15m = pt_breakout(df_15m)
    ema_15m = pt_ema_trend(df_15m)

    # BB mở rộng mạnh = squeeze đã giải phóng xong, chốt lời
    if (
        bb_15m["trang_thai"] == "MO_RONG"
        and bb_15m["bandwidth"] > bb_15m.get("mid_band", 0) * 0.015
    ):
        tin_hieu = "sell" if ema_15m["trang_thai"] == "TĂNG" else "buy"
        return (
            tin_hieu,
            20,
            f"BB mở rộng (BW={bb_15m['bandwidth']:.4f}) – squeeze hoàn thành",
        )

    # Breakout thất bại: bứt phá ngược chiều
    if brk_15m["trang_thai"] == "BREAK_DOWN" and ema_15m["trang_thai"] == "TĂNG":
        return "sell", 20, "Breakout thất bại – đảo chiều xuống"
    if brk_15m["trang_thai"] == "BREAK_OUT" and ema_15m["trang_thai"] == "GIẢM":
        return "buy", 20, "Breakout thất bại – đảo chiều lên"

    return None, 0, "Giữ lệnh"
