"""
utils/chuyen_doi_don_vi.py – Chuyển đổi đơn vị giao dịch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Các hàm tiện ích nhỏ dùng mọi nơi khi tính toán số lượng coin
và làm tròn khối lượng theo độ chính xác của từng sàn.
"""


def usdt_sang_so_luong_coin(so_tien_usdt, gia_coin):
    """Chuyển số tiền USDT sang số lượng coin tương đương."""
    if gia_coin == 0:
        return 0
    return so_tien_usdt / gia_coin


def mili_giay_sang_phut(ms):
    """Chuyển milliseconds sang phút – dùng để log thời gian xử lý."""
    return ms / (1000 * 60)


def lam_tron_khoi_luong(amount, precision_amount):
    """Làm tròn khối lượng theo số chữ số thập phân mà sàn yêu cầu."""
    return round(amount, precision_amount)
