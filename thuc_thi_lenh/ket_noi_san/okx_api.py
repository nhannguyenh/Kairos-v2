"""
thuc_thi_lenh/ket_noi_san/okx_api.py – Connector OKX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Wrapper CCXT cho OKX. Module-level instance okx_connector
được dùng trực tiếp khi cần gọi API OKX đặc thù.
Phần lớn lệnh nên đi qua BoMayThucThi để hỗ trợ đa sàn.
"""

import ccxt
from utils.doc_cau_hinh import lay_cau_hinh_api
from utils.log import logger


class OkxAPI:
    """Wrapper kết nối OKX qua CCXT, hỗ trợ set leverage với margin mode cross."""

    def __init__(self):
        """Khởi tạo kết nối OKX từ cấu hình API, gán None nếu không tìm thấy config."""
        configs = lay_cau_hinh_api()
        if "okx" in configs:
            self.exchange = ccxt.okx(configs["okx"])
            self.exchange.load_markets()
        else:
            self.exchange = None

    def doi_don_bay(self, symbol, leverage):
        """Set đòn bẩy cho symbol trên OKX với margin mode cross."""
        try:
            return self.exchange.set_leverage(
                leverage, symbol, params={"mgnMode": "cross"}
            )
        except Exception as e:
            logger.error(f"Lỗi set leverage OKX: {e}")
            return None


okx_connector = OkxAPI()
