"""
thuc_thi_lenh/chon_san_giao_dich.py – Chọn sàn giao dịch tối ưu
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Hiện đọc sàn ưu tiên từ config. Có thể mở rộng thành so sánh
spread/liquidity realtime giữa các sàn trong tương lai.
"""

from utils.doc_cau_hinh import lay_cau_hinh_giao_dich


def chon_san_tot_nhat(symbol):
    """Trả về tên sàn được cấu hình làm sàn chính trong cau_hinh_giao_dich.yaml."""
    config = lay_cau_hinh_giao_dich()
    uu_tien = config.get("san_giao_dich_chinh", "binance")
    return uu_tien
