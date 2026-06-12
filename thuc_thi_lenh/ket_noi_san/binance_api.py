"""
thuc_thi_lenh/ket_noi_san/binance_api.py – Connector Binance Futures
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Wrapper CCXT cho Binance. Module-level instance binance_connector
được dùng trực tiếp khi cần gọi API Binance đặc thù.
Phần lớn lệnh nên đi qua BoMayThucThi để hỗ trợ đa sàn.
"""

import ccxt
from utils.doc_cau_hinh import lay_cau_hinh_api
from utils.log import logger


class BinanceAPI:
    """Wrapper kết nối Binance qua CCXT, cung cấp các thao tác cơ bản."""

    def __init__(self):
        """Khởi tạo kết nối Binance từ cấu hình API, gán None nếu không tìm thấy config."""
        configs = lay_cau_hinh_api()
        if "binance" in configs:
            self.exchange = ccxt.binance(configs["binance"])
            self.exchange.load_markets()
        else:
            self.exchange = None

    def doi_don_bay(self, symbol, leverage):
        """Set đòn bẩy cho một symbol trên Binance."""
        try:
            return self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            logger.error(f"Lỗi set leverage Binance: {e}")
            return None

    def dat_lenh(self, symbol, side, amount, price=None):
        """Đặt lệnh market hoặc limit tùy theo có price hay không."""
        if not self.exchange:
            return None
        type = "limit" if price else "market"
        return self.exchange.create_order(symbol, type, side, amount, price)


binance_connector = BinanceAPI()
