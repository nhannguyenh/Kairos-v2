"""
ml/trang_thai_thi_truong_ml/ml_predict.py – Inference & đánh giá ML
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2 hàm chính:
  • du_doan_trang_thai_ml()        – dự đoán 1 cây nến (bar-to-bar, realtime)
  • danh_gia_ml()                  – ghi reward vào trading_memory.csv sau khi đóng lệnh

STATE_MAP định nghĩa 8 regime và chiến lược tương ứng:
  0 Đóng_Băng → không trade  |  1 Nén_Chặt → chờ breakout
  2 Đầu_XH → vào sớm         |  3 XH_Mạnh → follow trend
  4 Cao_Trào → chốt lời       |  5 Hồi_Quy → counter-trend
  6 Nhiễu_Động → range trade  |  7 Quét_TK → risk-off
"""

import os
import json
from datetime import datetime
import pandas as pd
import csv

# --- THƯ VIỆN LÕI ---
import torch
import numpy as np
import polars as pl

from ml.trang_thai_thi_truong_ml.ml_model import AI_Engine, DATA_DIR
from ml.trang_thai_thi_truong_ml.tao_feature import feature_dataset

LOG_FILE = os.path.join(DATA_DIR, "trading_memory.csv")
engine = AI_Engine()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


STATE_MAP = {
    0: "Đóng_Băng",  # Dead Market – không trade
    1: "Nén_Chặt",  # Squeeze – tích lũy nén, canh bứt phá
    2: "Đầu_Xu_Hướng",  # Early Trend – xu hướng chớm hình thành
    3: "Xu_Hướng_Mạnh",  # Strong Trend – H4/H1/M15 đồng thuận
    4: "Cao_Trào",  # Climax – giá chạy quá xa, sắp đảo chiều
    5: "Hồi_Quy",  # Mean Reversion – giật ngược về trung bình
    6: "Nhiễu_Động",  # Choppy – đi ngang biên độ hẹp
    7: "Quét_Thanh_Khoản",  # Liquidity Crisis – tin mạnh, risk-off
}

# Ánh xạ từ state_id sang tên chiến lược được dùng trong quan_ly_chien_luoc
STRATEGY_MAP = {
    0: None,  # Đóng_Băng  → không trade
    1: "Squeeze",  # Nén_Chặt   → đánh breakout khi squeeze nổ
    2: "Breakout",  # Đầu_XH     → vào sớm theo hướng breakout
    3: "Trend_following",  # XH_Mạnh    → follow trend đa khung
    4: "Mean_reversion",  # Cao_Trào   → đánh ngược khi kiệt sức
    5: "Mean_reversion",  # Hồi_Quy    → đánh ngược về trung bình
    6: "Scalping",  # Nhiễu_Động → scalp biên độ hẹp
    7: None,  # Quét_TK    → quá nguy hiểm, không trade
}


def du_doan_trang_thai_ml(df_5m, df_15m, df_1h, df_4h, last_state=None):
    """Dự đoán regime hiện tại (bar-to-bar) từ 4 khung thời gian; trả về ML packet hoặc None."""
    # BƯỚC 1: Xây dựng bộ đặc trưng (Feature Dataset) từ 4 khung thời gian 5m, 15m, 1h, 4h
    # Truyền kèm last_state (Teacher's previous regime) để duy trì context bộ nhớ
    feature_dict = feature_dataset(df_5m, df_15m, df_1h, df_4h, last_state=last_state)

    # Nếu không có hoặc thiếu dữ liệu tính toán chỉ báo, trả về None (Bypass không trade)
    if feature_dict is None or (
        isinstance(feature_dict, pd.DataFrame) and feature_dict.empty
    ):
        return None

    # BƯỚC 2: Trích xuất dòng dữ liệu cuối cùng (Latest candle) đại diện cho thời điểm hiện tại
    input_vector = {k: v.iloc[-1] for k, v in feature_dict.items()}

    # BƯỚC 3: Gọi AI Engine thực hiện suy diễn lớp phân loại
    # Trả về mã trạng thái (state_id), độ tự tin (conf) và xác suất phân phối (probs)
    state_id, conf, probs = engine.predict(input_vector)

    if state_id is None:
        return None

    # BƯỚC 4: Định tuyến chiến lược giao dịch dựa trên regime dự đoán của AI
    strategy = STRATEGY_MAP.get(state_id)

    # Nếu trạng thái thị trường thuộc nhóm rủi ro cao hoặc đóng băng (strategy = None) -> Đứng ngoài
    if strategy is None:
        return None

    # BƯỚC 5: Đóng gói gói tin kết quả ML (ML Packet) để chuyển tiếp sang bộ điều phối chiến lược
    packet = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "state_id": state_id,
        "state_name": STATE_MAP.get(state_id, "UNKNOWN"),
        "strategy_name": strategy,  # tên chiến lược để quan_ly_chien_luoc điều phối (routing)
        "confidence": round(conf, 4),
        "probs": probs,
        "features_snapshot": input_vector,
    }
    return packet



def danh_gia_ml(packet, pnl, dd, correct=None):
    """Tính reward từ PnL/DD và ghi vào trading_memory.csv để phục vụ self-supervised learning."""
    # Nếu không có thông tin gói tin ML, dừng xử lý
    if not packet:
        return

    if correct is None:
        correct = "NaN"

    state_name = packet["state_name"]

    # BƯỚC 1: Tính toán phần thưởng cơ bản (Base Reward) dựa trên PnL thực tế của vị thế
    # Vì mục tiêu là bảo toàn vốn, lệnh thua lỗ (PnL < 0) bị phạt nặng hơn gấp đôi (penalty weight = 2.0)
    if pnl > 0:
        reward = pnl * 1.0
    else:
        reward = pnl * 2.0

    # BƯỚC 2: Điều chỉnh phần thưởng theo tính chất đặc thù của từng chiến lược (Regime-specific Adjustments)
    if state_name == "Nhiễu_Động":  # Regime 6 – Scalping: Đánh sóng ngắn hẹp
        if pnl < 0:
            reward -= 2.0
        elif 0 < pnl < 0.5:
            reward += 0.5
    elif state_name in (
        "Nén_Chặt",
        "Đầu_Xu_Hướng",
    ):  # Regime 1,2 – Breakout: Bứt phá, yêu cầu biên lợi nhuận lớn
        if pnl < 0:
            reward -= 2.0
        elif pnl > 2.0:
            reward += 2.0
    elif (
        state_name == "Xu_Hướng_Mạnh"
    ):  # Regime 3 – Trend Following: Bám xu hướng dài, kỳ vọng lợi nhuận cực lớn
        if pnl < 0:
            reward *= 1.5
        elif pnl > 3.0:
            reward += 3.0
    elif state_name in (
        "Cao_Trào",
        "Hồi_Quy",
    ):  # Regime 4,5 – Mean Reversion: Đánh ngược xu hướng khi quá mua/quá bán
        if pnl < -1.0:
            reward -= 3.0
        elif pnl > 1.5:
            reward += 2.0
    else:
        # Nếu sụt giảm tài khoản sâu (Max Drawdown < -1%), áp hình phạt giảm điểm
        if dd < -1.0:
            reward -= 1.0

    # BƯỚC 3: Giới hạn phần thưởng trong biên độ an toàn [-10, 10] tránh bùng nổ gradient
    reward = max(min(reward, 10), -10)

    # BƯỚC 4: Ghi nhật ký chi tiết của lệnh kèm toàn bộ snapshot features tại thời điểm vào lệnh
    # Tệp log này sẽ làm nguyên liệu đầu vào giúp mô hình tự học (Self-supervised learning) sau này
    log_row = {
        "timestamp": packet["timestamp"],
        "state": packet["state_id"],
        "correct": correct,
        "state_name": packet["state_name"],
        "confidence": packet["confidence"],
        "pnl": round(pnl, 4),
        "reward": round(reward, 4),
        "features_json": json.dumps(packet["features_snapshot"]),
    }

    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=log_row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(log_row)
