"""TÂM LÝ & VỊ THẾ (Sentiment / Positioning)
👉 Đám đông đang nghiêng về đâu?
- Funding Rate
- Open Interest
- Long/Short Ratio
- CVD (Cumulative Volume Delta)
- Fear & Greed Index
📌 Dùng để:
- Tránh vào lệnh ngược "cá mập"
- Phát hiện squeeze
- Hệ thống pro level"""


def pt_funding_rate(snapshot):
    """Phân tích Funding Rate từ WebSocket: FR > 0 = overlong, FR < 0 = overshort."""
    if not snapshot:
        return None

    fr = snapshot.get("funding_rate", 0.0)

    if fr >= 0.0015:
        trang_thai, muc_do = (
            "LONG_QUA_MUC",
            "EXTREME",
        )  # > 0.15% – nguy cơ thanh lý long hàng loạt
    elif fr >= 0.0005:
        trang_thai, muc_do = "LONG_NHIEU", "CAO"  # 0.05%–0.15%
    elif fr <= -0.0015:
        trang_thai, muc_do = "SHORT_QUA_MUC", "EXTREME"  # < -0.15%
    elif fr <= -0.0005:
        trang_thai, muc_do = "SHORT_NHIEU", "CAO"
    else:
        trang_thai, muc_do = "TRUNG_TINH", "THAP"

    return {
        "gia_tri": fr,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_cvd(snapshot):
    """Phân tích CVD từ @aggTrade: buy_ratio > 0.60 = lực mua áp đảo trong phiên."""
    if not snapshot:
        return None

    buy_vol = snapshot.get("buy_vol", 0.0)
    sell_vol = snapshot.get("sell_vol", 0.0)
    delta = snapshot.get("delta", 0.0)
    total = buy_vol + sell_vol

    if total < 1e-9:
        return None

    buy_ratio = buy_vol / total

    if buy_ratio >= 0.60:
        trang_thai, muc_do = "MUA_MANH", "CAO"
    elif buy_ratio >= 0.52:
        trang_thai, muc_do = "NGHIENG_MUA", "THAP"
    elif buy_ratio <= 0.40:
        trang_thai, muc_do = "BAN_MANH", "CAO"
    elif buy_ratio <= 0.48:
        trang_thai, muc_do = "NGHIENG_BAN", "THAP"
    else:
        trang_thai, muc_do = "CAN_BANG", "THAP"

    return {
        "gia_tri": round(delta, 2),
        "buy_ratio": round(buy_ratio, 4),
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_imbalance(snapshot):
    """Phân tích Order Book Imbalance từ @depth5: imbalance > 0 = bid dày hơn ask."""
    if not snapshot:
        return None

    imbalance = snapshot.get("imbalance", 0.0)
    bid_total = snapshot.get("bid_total", 0.0)
    ask_total = snapshot.get("ask_total", 0.0)

    if bid_total + ask_total < 1e-9:
        return None

    if imbalance >= 0.30:
        trang_thai, muc_do = "AP_LUC_MUA_MANH", "CAO"
    elif imbalance >= 0.10:
        trang_thai, muc_do = "NGHIENG_MUA", "THAP"
    elif imbalance <= -0.30:
        trang_thai, muc_do = "AP_LUC_BAN_MANH", "CAO"
    elif imbalance <= -0.10:
        trang_thai, muc_do = "NGHIENG_BAN", "THAP"
    else:
        trang_thai, muc_do = "CAN_BANG", "THAP"

    return {
        "gia_tri": round(imbalance, 4),
        "bid_total": round(bid_total, 2),
        "ask_total": round(ask_total, 2),
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_liquidation(snapshot):
    """Phân tích Liquidation từ @forceOrder: short squeeze khi liq_short >> liq_long."""
    if not snapshot:
        return None

    liq_long = snapshot.get("liq_long", 0.0)
    liq_short = snapshot.get("liq_short", 0.0)
    total = liq_long + liq_short

    if total < 1e-9:
        return {
            "gia_tri": 0.0,
            "liq_long": 0.0,
            "liq_short": 0.0,
            "trang_thai": "IM_LANG",
            "muc_do": "THAP",
        }

    if liq_short > liq_long * 2.5:
        trang_thai = "SHORT_SQUEEZE"  # short bị bắn → momentum tăng
    elif liq_long > liq_short * 2.5:
        trang_thai = "LONG_LIQUIDATION"  # long bị thanh lý → momentum giảm
    else:
        trang_thai = "BINH_THUONG"

    muc_do = "CAO" if total > 50 else "THAP"

    return {
        "gia_tri": round(total, 2),
        "liq_long": round(liq_long, 2),
        "liq_short": round(liq_short, 2),
        "trang_thai": trang_thai,
        "muc_do": muc_do,
    }


def pt_vi_the(snapshot):
    """Tổng hợp Funding Rate + CVD + Order Book + Liquidation thành điểm tâm lý [-10, +10]."""
    fr = pt_funding_rate(snapshot)
    cvd = pt_cvd(snapshot)
    imb = pt_imbalance(snapshot)
    liq = pt_liquidation(snapshot)

    diem = 0
    ly_do = []

    # Funding Rate tác động NGƯỢC chiều (FR cao → thị trường overlong → nguy cơ đảo chiều giảm)
    if fr:
        if fr["trang_thai"] == "LONG_QUA_MUC":
            diem -= 4
            ly_do.append(f"FR cực cao {fr['gia_tri']:.4f} → overlong")
        elif fr["trang_thai"] == "LONG_NHIEU":
            diem -= 2
            ly_do.append(f"FR cao {fr['gia_tri']:.4f} → nhiều long")
        elif fr["trang_thai"] == "SHORT_QUA_MUC":
            diem += 4
            ly_do.append(f"FR cực âm {fr['gia_tri']:.4f} → overshort")
        elif fr["trang_thai"] == "SHORT_NHIEU":
            diem += 2
            ly_do.append(f"FR âm {fr['gia_tri']:.4f} → nhiều short")

    # CVD tác động THUẬN chiều (mua nhiều → tăng điểm bullish)
    if cvd:
        if cvd["trang_thai"] == "MUA_MANH":
            diem += 3
            ly_do.append(f"CVD mua mạnh {cvd['buy_ratio']:.0%}")
        elif cvd["trang_thai"] == "NGHIENG_MUA":
            diem += 1
            ly_do.append(f"CVD nghiêng mua {cvd['buy_ratio']:.0%}")
        elif cvd["trang_thai"] == "BAN_MANH":
            diem -= 3
            ly_do.append(f"CVD bán mạnh {cvd['buy_ratio']:.0%}")
        elif cvd["trang_thai"] == "NGHIENG_BAN":
            diem -= 1
            ly_do.append(f"CVD nghiêng bán {cvd['buy_ratio']:.0%}")

    # Order Book tác động THUẬN chiều
    if imb:
        if imb["trang_thai"] == "AP_LUC_MUA_MANH":
            diem += 2
            ly_do.append(f"OrderBook bid >> ask ({imb['gia_tri']:.2f})")
        elif imb["trang_thai"] == "NGHIENG_MUA":
            diem += 1
            ly_do.append(f"OrderBook nghiêng mua ({imb['gia_tri']:.2f})")
        elif imb["trang_thai"] == "AP_LUC_BAN_MANH":
            diem -= 2
            ly_do.append(f"OrderBook ask >> bid ({imb['gia_tri']:.2f})")
        elif imb["trang_thai"] == "NGHIENG_BAN":
            diem -= 1
            ly_do.append(f"OrderBook nghiêng bán ({imb['gia_tri']:.2f})")

    # Liquidation tác động THUẬN chiều squeeze
    if liq:
        if liq["trang_thai"] == "SHORT_SQUEEZE" and liq["muc_do"] == "CAO":
            diem += 3
            ly_do.append(f"Short squeeze {liq['liq_short']:.1f}")
        elif liq["trang_thai"] == "LONG_LIQUIDATION" and liq["muc_do"] == "CAO":
            diem -= 3
            ly_do.append(f"Long liquidation {liq['liq_long']:.1f}")

    trang_thai = "BULLISH" if diem > 0 else "BEARISH" if diem < 0 else "TRUNG_TINH"
    muc_do = "MANH" if abs(diem) >= 5 else "YEU"

    return {
        "diem": diem,
        "trang_thai": trang_thai,
        "muc_do": muc_do,
        "ly_do": "; ".join(ly_do),
        "funding_rate": fr,
        "cvd": cvd,
        "imbalance": imb,
        "liquidation": liq,
    }
