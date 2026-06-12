"""
thuc_thi_lenh/mo_lenh.py – Đặt lệnh mở vị thế
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Wrapper thực thi lệnh market/limit qua CCXT, tự động set đòn bẩy trước.
Trả về order object của sàn hoặc None nếu lỗi.
"""

from thuc_thi_lenh.bo_may_thuc_thi import quan_ly_san
from utils.log import logger


def thuc_hien_mo_lenh(
    san, symbol, side, khoi_luong, loai_lenh="market", gia=None, don_bay=1, params={}
):
    """Mở lệnh market/limit, tự set leverage. Nuốt lỗi set_leverage vì một số sàn không cần."""
    exchange = quan_ly_san.lay_san(san)
    if not exchange:
        logger.error(f"Không tìm thấy kết nối sàn {san}")
        return None

    try:
        try:
            exchange.set_leverage(don_bay, symbol)
        except:
            pass
        order = exchange.create_order(
            symbol, loai_lenh, side, khoi_luong, gia, params=params
        )

        logger.info(f"MỞ LỆNH {side.upper()} {symbol} thành công. ID: {order['id']}")
        return order
    except Exception as e:
        logger.error(f"Lỗi mở lệnh {symbol}: {e}")
        return None
