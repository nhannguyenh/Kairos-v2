"""
thuc_thi_lenh/mo_lenh_da_san.py – Phân bổ lệnh ra nhiều sàn
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Chia đều khối lượng lệnh ra nhiều sàn để giảm slippage hoặc arbitrage.
Mặc định sử dụng Binance và OKX nếu không truyền danh sách sàn.
"""

from thuc_thi_lenh.mo_lenh import thuc_hien_mo_lenh
from utils.log import logger


def mo_lenh_phan_bo_da_san(symbol, side, tong_khoi_luong, danh_sach_san=None):
    """Phân bổ khối lượng lệnh ra nhiều sàn để giảm trượt giá (Slippage) hoặc Arbitrage."""
    if danh_sach_san is None:
        danh_sach_san = ["binance", "okx"]
    if not danh_sach_san:
        logger.warning("Danh sách sàn rỗng, không thực hiện lệnh.")
        return {}
    kl_moi_san = tong_khoi_luong / len(danh_sach_san)
    ket_qua = {}

    for san in danh_sach_san:
        logger.info(f"Phân bổ {kl_moi_san} {symbol} sang {san}")
        order = thuc_hien_mo_lenh(san, symbol, side, kl_moi_san)
        if order:
            ket_qua[san] = order["id"]
        else:
            ket_qua[san] = "Failed"

    return ket_qua
