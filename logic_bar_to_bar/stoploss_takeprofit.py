"""
chien_luoc/logic_bar_to_bar/stoploss_takeprofit.py – Tính SL/TP theo ATR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SL/TP động thay vì cố định %. Công thức:
  he_so_sl = base_sl * vol_ratio  (clamp [1.0, 6.0])
  SL = entry ± ATR * he_so_sl
  TP = entry ± ATR * he_so_sl * RR

Khi thị trường volatile cao (ATR > ATR_mean), khoảng SL rộng hơn để
tránh bị quét stop do noise. RR mặc định 2:1.
"""

from logic_bar_to_bar.phan_tich_ky_thuat.bien_dong import pt_atr


def tinh_sl_tp_theo_atr(gia_vao, side, df):
    """Tính giá dừng lỗ và chốt lời động theo ATR. Trả về (sl, tp) hoặc (None, None)."""
    # BƯỚC 1: Lấy giá trị biến động ATR và trung bình ATR hiện tại
    ket_qua = pt_atr(df)
    atr = ket_qua["atr_val"]
    atr_mean = ket_qua["atr_mean"]

    # Nếu không có dữ liệu biến động hợp lệ, không thực hiện đặt SL/TP
    if atr is None or atr <= 0:
        return None, None

    # BƯỚC 2: Tính tỷ lệ biến động (Volatility Ratio)
    # Tỷ lệ này đo lường biến động hiện tại so với trung bình quá khứ
    if atr_mean is None or atr_mean <= 0:
        vol_ratio = 1.0
    else:
        vol_ratio = atr / atr_mean

    # ===== CẤU HÌNH CƠ BẢN (BASE CONFIG) =====

    # | Kiểu trade | base_sl       | rr        | Ghi chú
    # | ---------- | ------------- | --------- | -------------------------
    # | Scalping   | 1.5 – 2.0     | 1.5       | Giá sai là cắt liền
    # | Intraday   | 2.0 – 2.5     | 2.0       | Rung được chút, đi đúng là giữ
    # | Swing      | 3.0 – 4.0     | 2.5 – 3.0 | Rung mạnh cũng kệ, miễn trend còn

    base_sl = 2.7  # base_sl càng LỚN → khoảng SL & TP càng RỘNG
    rr = 2.0  # Tỷ lệ Rủi ro : Lợi nhuận (Risk-Reward Ratio)

    # BƯỚC 3: Tính toán hệ số nhân khoảng cách SL
    # vol_ratio > 1 = biến động cao → SL rộng hơn để không bị noise quét stop
    he_so_sl = base_sl * vol_ratio

    # Giới hạn hệ số nhân trong khoảng an toàn [1.0, 6.0] tránh khoảng cách quá lớn hoặc quá bé
    he_so_sl = max(1.0, min(he_so_sl, 6.0))
    he_so_tp = he_so_sl * rr

    # BƯỚC 4: Tính tỷ lệ phần trăm khoảng cách SL và TP so với giá vào lệnh
    sl_pct = (atr * he_so_sl) / gia_vao
    tp_pct = (atr * he_so_tp) / gia_vao

    # Giới hạn tỷ lệ phần trăm tối đa/tối thiểu (SL: 0.5% - 15%, TP: 1% - 30%)
    # Giúp bảo vệ tài khoản khi xảy ra râu nến bất thường hoặc tin tức giật cực mạnh
    sl_pct = max(0.005, min(sl_pct, 0.15))
    tp_pct = max(0.01, min(tp_pct, 0.30))

    # BƯỚC 5: Tính giá trị dừng lỗ / chốt lời thực tế dựa trên vị thế Long (Buy) hay Short (Sell)
    if side == "buy":
        sl = gia_vao * (1 - sl_pct)
        tp = gia_vao * (1 + tp_pct)
    else:  # sell
        sl = gia_vao * (1 + sl_pct)
        tp = gia_vao * (1 - tp_pct)

    return sl, tp
