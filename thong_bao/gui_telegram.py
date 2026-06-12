"""
thong_bao/gui_telegram.py – Thông báo Telegram
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Gửi alert khi bot mở/đóng lệnh. Tự bỏ qua nếu TOKEN chưa được cấu hình.
Điền TOKEN và CHAT_ID vào để nhận thông báo realtime trên điện thoại.
"""

import requests
from utils.log import logger

TOKEN = "TOKEN_TELEGRAM_CUA_BAN"
CHAT_ID = "CHAT_ID_CUA_BAN"


def gui_tin_nhan_telegram(tin_nhan):
    """Gửi tin nhắn văn bản đến Telegram, bỏ qua nếu TOKEN chưa được cấu hình."""
    if "TOKEN" in TOKEN:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": tin_nhan})
    except Exception as e:
        logger.error(f"Lỗi gửi Telegram: {e}")
